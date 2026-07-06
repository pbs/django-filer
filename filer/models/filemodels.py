import hashlib
import mimetypes
import os
import logging
from datetime import datetime, timezone

from django.conf import settings
from django.contrib.auth import models as auth_models
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import models, IntegrityError, transaction
from django.db.models import DEFERRED, Count
from django.urls import NoReverseMatch, reverse
from django.utils.functional import cached_property
from django.utils import timezone as django_timezone
from django.utils.translation import gettext_lazy as _

from polymorphic.managers import PolymorphicManager
from polymorphic.models import PolymorphicModel
from polymorphic.query import PolymorphicQuerySet

from .. import settings as filer_settings
from ..fields.multistorage_file import MultiStorageFileField
from ..utils.cache import invalidate_folder_listing_cache, invalidate_folder_listing_cache_for_file
from ..utils.cms_roles import (
    get_sites_without_restriction_perm,
    has_admin_role,
    has_role_on_site,
    can_restrict_on_site,
)
from ..utils.files import matching_file_subtypes
from . import mixins

import filer

logger = logging.getLogger(__name__)


def silence_error_if_missing_file(exception):
    """
    Ugly way of checking if an exception describes a 'missing file'.
    """
    missing_files_errs = ('no such file', 'does not exist',)

    def find_msg_in_error(msg):
        return msg in str(exception).lower()

    if not any(map(find_msg_in_error, missing_files_errs)):
        raise exception


class FileQuerySet(PolymorphicQuerySet):
    def only(self, *fields):
        fields = set(fields)
        fields.update(["_file_size", "sha1", "is_public"])
        return super().only(*fields)

    # PBS-specific querysets
    def readonly(self, user):
        Folder = filer.models.foldermodels.Folder
        return self.filter(folder__folder_type=Folder.CORE_FOLDER)

    def find_duplicates(self, file_obj):
        return self.exclude(pk=file_obj.pk).filter(sha1=file_obj.sha1)

    def restricted(self, user):
        sites = get_sites_without_restriction_perm(user)
        if not sites:
            return self.none()
        return self.filter(
            restricted=True,
            folder__site__in=sites)

    def unrestricted(self, user):
        sites = get_sites_without_restriction_perm(user)
        if not sites:
            return self
        return self.exclude(
            restricted=True,
            folder__site__in=sites)


class FileManager(PolymorphicManager):
    queryset_class = FileQuerySet

    # Proxy all unknown method calls to the queryset
    def __getattr__(self, name):
        if name.startswith('__'):
            return super(PolymorphicManager, self).__getattr__(self, name)
        return getattr(self.all(), name)

    def find_all_duplicates(self):
        return {file_data['sha1']: file_data['count']
                for file_data in self.get_queryset().values('sha1').annotate(
                    count=Count('id')).filter(count__gt=1)}

    def find_duplicates(self, file_obj):
        return [i for i in self.exclude(pk=file_obj.pk).filter(sha1=file_obj.sha1)]


# PBS-specific managers for trash system
class AliveFileManager(FileManager):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class TrashFileManager(FileManager):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=False)


def is_public_default():
    # not using this setting directly as `is_public` default value
    # so that Django doesn't generate new migrations upon setting change
    return filer_settings.FILER_IS_PUBLIC_DEFAULT


def mimetype_validator(value):
    if not mimetypes.guess_extension(value):
        msg = "'{mimetype}' is not a recognized MIME-Type."
        raise ValidationError(msg.format(mimetype=value))


@mixins.trashable
class File(PolymorphicModel, mixins.IconsMixin):
    file_type = 'File'
    _icon = 'file'
    _file_data_changed_hint = None

    folder = models.ForeignKey(
        'filer.Folder',
        verbose_name=_("folder"),
        related_name='all_files',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )

    file = MultiStorageFileField(
        _("file"),
        null=True,
        blank=True,
        db_index=True,
        max_length=1024,
    )

    _file_size = models.BigIntegerField(
        _("file size"),
        null=True,
        blank=True,
    )

    sha1 = models.CharField(
        _("sha1"),
        max_length=40,
        blank=True,
        default='',
    )

    has_all_mandatory_data = models.BooleanField(
        _("has all mandatory data"),
        default=False,
        editable=False,
    )

    original_filename = models.CharField(
        _("original filename"),
        max_length=255,
        blank=True,
        null=True,
    )

    name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_("file name"),
        help_text=_('Change the FILE name for an image in the cloud storage'
                    ' system; be sure to include the extension '
                    '(.jpg or .png, for example) to ensure asset remains '
                    'valid.'),
    )

    title = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_("name"),
        help_text=_('Used in the Photo Gallery plugin as a title or name for'
                    ' an image; not displayed via the image plugin.'),
    )

    description = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("description"),
        help_text=_('Used in the Photo Gallery plugin as a description;'
                    ' not displayed via the image plugin.'),
    )

    owner = models.ForeignKey(
        getattr(settings, 'AUTH_USER_MODEL', 'auth.User'),
        related_name='owned_%(class)ss',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("owner"),
    )

    uploaded_at = models.DateTimeField(
        _("uploaded at"),
        auto_now_add=True,
    )

    modified_at = models.DateTimeField(
        _("modified at"),
        auto_now=True,
    )

    is_public = models.BooleanField(
        default=filer_settings.FILER_IS_PUBLIC_DEFAULT,
        verbose_name=_("Permissions disabled"),
        help_text=_("Disable any permission checking for this "
                    "file. File will be publicly accessible "
                    "to anyone."),
    )

    mime_type = models.CharField(
        max_length=255,
        help_text="MIME type of uploaded content",
        validators=[mimetype_validator],
        default='application/octet-stream',
    )

    # PBS-specific: restricted field
    restricted = models.BooleanField(
        _("Restrict Editors and Writers from being able to edit "
          "or delete this asset"), default=False,
        help_text=_('If this box is checked, '
                    'Editors and Writers will still be able to '
                    'view the asset, add it to a plugin or smart '
                    'snippet but will not be able to delete or '
                    'modify the current version of the asset.'),
    )

    # PBS-specific: trash managers
    objects = AliveFileManager()
    trash = TrashFileManager()
    all_objects = FileManager()

    class Meta:
        app_label = 'filer'
        verbose_name = _("file")
        verbose_name_plural = _("files")

    @classmethod
    def matches_file_type(cls, iname, ifile, request):
        return True  # I match all files...

    # Sentinel for fields whose previous value is unknown (deferred).
    # Using a dedicated sentinel instead of substituting empty defaults
    # prevents false positives in change-detection that could trigger
    # unnecessary file copies/moves on storage.
    _UNKNOWN = object()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # PBS: Use __dict__ to avoid triggering deferred field loading
        # which can cause recursion in Django 5.1+ (from_db calls __init__).
        raw_is_public = self.__dict__.get('is_public', DEFERRED)
        if raw_is_public is DEFERRED:
            if self.pk is not None:
                self._old_is_public = self.__class__.all_objects.filter(
                    pk=self.pk
                ).values_list('is_public', flat=True).first()
            else:
                self._old_is_public = False
        else:
            self._old_is_public = raw_is_public
        raw_sha1 = self.__dict__.get('sha1', DEFERRED)
        self._old_sha1 = self._UNKNOWN if raw_sha1 is DEFERRED else raw_sha1
        self._force_commit = False
        # see method _is_path_changed
        raw_name = self.__dict__.get('name', DEFERRED)
        self._old_name = self._UNKNOWN if raw_name is DEFERRED else raw_name
        # For FileField, the raw value in __dict__ is the file name string
        file_val = self.__dict__.get('file', '')
        if file_val is DEFERRED:
            file_val = ''
        if file_val and hasattr(file_val, 'name'):
            self._current_file_location = file_val.name
        else:
            self._current_file_location = file_val or ''
        raw_folder_id = self.__dict__.get('folder_id', DEFERRED)
        self._old_folder_id = self._UNKNOWN if raw_folder_id is DEFERRED else raw_folder_id

    @cached_property
    def mime_maintype(self):
        return self.mime_type.split('/')[0]

    @cached_property
    def mime_subtype(self):
        return self.mime_type.split('/')[1]

    def file_data_changed(self, post_init=False):
        """
        This is called whenever self.file changes (including initial set in __init__).
        Returns True if data related attributes were updated, False otherwise.
        """
        if self._file_data_changed_hint is not None:
            data_changed_hint = self._file_data_changed_hint
            self._file_data_changed_hint = None
            if not data_changed_hint:
                return False
        if post_init and self._file_size and self.sha1:
            return False
        try:
            self._file_size = self.file.size
        except:   # noqa
            self._file_size = None
        try:
            self.generate_sha1()
        except Exception:
            self.sha1 = ''
        try:
            self.mime_type = mimetypes.guess_type(self.file.name)[0] or 'application/octet-stream'
        except Exception:
            pass
        return True

    def clean(self):
        if self.name:
            self.name = self.name.strip()
            if "/" in self.name:
                raise ValidationError(
                    "Slashes are not allowed in file names.")
            extension = os.path.splitext(self.name)[1]
            if not extension:
                raise ValidationError(
                    "File name without extension is not allowed.")

            old_file_type = self.get_real_instance_class()
            new_file_type = matching_file_subtypes(self.name, None, None)[0]

            if old_file_type is not new_file_type:
                supported_extensions = getattr(
                    old_file_type, '_filename_extensions', [])
                if supported_extensions:
                    err_msg = "File name (%s) for this %s should preserve " \
                              "one of the supported extensions %s" % (
                                self.name, old_file_type.file_type.lower(),
                                ', '.join(supported_extensions))
                else:
                    err_msg = "Extension %s is not allowed for this file " \
                              "type." % (extension,)
                raise ValidationError(err_msg)

        if self.folder:
            entries = self.folder.entries_with_names([self.actual_name])
            if entries and any(entry.pk != self.pk for entry in entries):
                raise ValidationError(
                    _('Current folder already contains a file named %s') %
                    self.actual_name)

    def _move_file(self):
        """
        Move the file from src to dst.
        """
        src_file_name = self.file.name
        dst_file_name = self._meta.get_field('file').generate_filename(
            self, self.original_filename)

        if self.is_public:
            src_storage = self.file.storages['private']
            dst_storage = self.file.storages['public']
        else:
            src_storage = self.file.storages['public']
            dst_storage = self.file.storages['private']

        # delete the thumbnail
        self.is_public = not self.is_public
        self.file.delete_thumbnails()
        self.is_public = not self.is_public
        src_file = src_storage.open(src_file_name)
        with src_file.open() as f:
            content_file = ContentFile(f.read())
        self._file_data_changed_hint = False
        self.file = dst_storage.save(dst_file_name, content_file)
        src_storage.delete(src_file_name)

    def _copy_file(self, destination, overwrite=False):
        """
        Copies the file to a destination files and returns it.
        """
        if overwrite:
            raise NotImplementedError

        src_file_name = self._current_file_location
        storage = self.file.storages['public' if self.is_public else 'private']

        if hasattr(storage, 'copy'):
            storage.copy(src_file_name, destination)
        else:
            src_file = storage.open(src_file_name)
            src_file.open()
            file_content = src_file.read()
            src_file.close()
            if storage.exists(destination):
                storage.delete(destination)
            destination = storage.save(destination,
                                       ContentFile(file_content, name=os.path.basename(destination)))
        self._current_file_location = destination
        self._old_name = self.name
        self._old_folder_id = getattr(self.folder, 'id', None)
        return destination

    def generate_sha1(self):
        sha = hashlib.sha1()
        self.file.seek(0)
        while True:
            buf = self.file.read(104857600)
            if not buf:
                break
            sha.update(buf)
        self.sha1 = sha.hexdigest()
        self.file.seek(0)

    # PBS-specific: set restricted from folder
    def set_restricted_from_folder(self):
        if self.folder and self.folder.restricted:
            self.restricted = self.folder.restricted

    def save(self, *args, **kwargs):
        self.set_restricted_from_folder()
        # check if this is a subclass of "File" or not and set
        # _file_type_plugin_name
        if self.__class__ == File:
            pass
        elif issubclass(self.__class__, File):
            self._file_type_plugin_name = self.__class__.__name__
        # Ensure file metadata is computed on first save
        if not self.sha1 and self.file:
            self.file_data_changed()
        # cache the file size
        try:
            self._file_size = self.file.size
        except:
            pass
        if self._old_is_public != self.is_public and self.pk:
            self._move_file()
            self._old_is_public = self.is_public

        # generate SHA1 hash
        try:
            self.generate_sha1()
        except (IOError, TypeError, ValueError):
            pass
        replaced_file = (self._old_sha1 is not self._UNKNOWN and
                         self._old_sha1 != self.sha1)
        # Track old folder for cache invalidation when file moves between folders
        old_folder_id = self._old_folder_id
        if filer_settings.FOLDER_AFFECTS_URL and (self._is_path_changed() or replaced_file):
            if replaced_file and not self._is_name_changed():
                self.name = None
            self._force_commit = True
            self.update_location_on_storage(*args, **kwargs)
        else:
            super().save(*args, **kwargs)
        # Invalidate cache for the current folder
        invalidate_folder_listing_cache_for_file(self)
        # If file moved between folders, also invalidate the old folder
        new_folder_id = getattr(self.folder, 'id', None)
        if (old_folder_id is not self._UNKNOWN and
                old_folder_id and old_folder_id != new_folder_id):
            try:
                old_folder = filer.models.foldermodels.Folder.all_objects.get(
                    id=old_folder_id)
                invalidate_folder_listing_cache(old_folder)
            except filer.models.foldermodels.Folder.DoesNotExist:
                pass

    save.alters_data = True

    def _is_name_changed(self):
        """Check if the file name was explicitly changed by the user."""
        if self._old_name is self._UNKNOWN:
            return False  # can't determine change from deferred field
        if self._old_name in ('', None):
            return self.name not in ('', None)
        return self._old_name != self.name

    def _is_path_changed(self):
        """
        Used to detect if file location on storage should be updated or not.
        """
        # If previous values are unknown (deferred), skip change-detection
        # to avoid triggering unnecessary file copies/moves on storage.
        if self._old_name is self._UNKNOWN or self._old_folder_id is self._UNKNOWN:
            return False

        # check if file name changed
        if self._old_name in ('', None):
            name_changed = self.name not in ('', None)
        else:
            name_changed = self._old_name != self.name

        folder_changed = self._old_folder_id != getattr(self.folder, 'id', None)
        return name_changed or folder_changed

    def _delete_thumbnails(self):
        source = self.file.get_source_cache()
        if source:
            self.file.delete_thumbnails()
            source.delete()

    def update_location_on_storage(self, *args, **kwargs):
        old_location = self._current_file_location
        self._delete_thumbnails()
        if self._old_sha1 != self.sha1:
            # actual file content needs to be replaced on storage prior to
            #   filer file instance save
            if self._current_file_location:
                self.file.storage.save(self._current_file_location, self.file)
            else:
                # New file — save to the computed target location directly
                target = self.file.field.upload_to(self, self.upload_to_name)
                saved_target = self.file.storage.save(target, self.file)
                self._current_file_location = saved_target
                self.file.name = saved_target
            self._old_sha1 = self.sha1
        new_location = self.file.field.upload_to(self, self.upload_to_name)
        storage = self.file.storage

        def copy_and_save():
            saved_as = self._copy_file(new_location)
            assert saved_as == new_location, '%s %s' % (saved_as, new_location)
            self._file_data_changed_hint = False
            self.file = saved_as
            super(File, self).save(*args, **kwargs)

        if self._force_commit:
            try:
                with transaction.atomic(savepoint=False):
                    copy_and_save()
            except:
                # delete the file from new_location if the db update failed
                if old_location and old_location != new_location:
                    storage.delete(new_location)
                raise
            else:
                # only delete the file on the old_location if all went OK
                if old_location and old_location != new_location:
                    storage.delete(old_location)
        else:
            copy_and_save()
        return new_location

    # PBS-specific: soft delete / trash system
    def soft_delete(self, *args, **kwargs):
        """
        Soft-delete: moves file to trash location on storage.
        """
        deletion_time = kwargs.pop('deletion_time', django_timezone.now())
        to_trash = filer.utils.generate_filename.get_trash_path(self)
        old_location, new_location = self.file.name, None
        try:
            new_location = self._copy_file(to_trash)
        except Exception as e:
            silence_error_if_missing_file(e)
            if filer_settings.FILER_ENABLE_LOGGING:
                logger.error('Error while trying to copy file: %s to %s.' % (
                    old_location, to_trash), e)
        else:
            if not File.objects.exclude(pk=self.pk).filter(
                file=old_location, is_public=self.is_public).exists():
                self.file.delete(False)
        finally:
            new_location = new_location or to_trash
            File.objects.filter(pk=self.pk).update(
                deleted_at=deletion_time, file=new_location)
            self.deleted_at = deletion_time
            self.file = new_location
        # Invalidate cache for the folder this file was in
        invalidate_folder_listing_cache_for_file(self)

    def hard_delete(self, *args, **kwargs):
        """
        Hard-delete: removes from DB and storage.
        """
        super().delete(*args, **kwargs)
        if not File.objects.filter(file=self.file.name,
                                   is_public=self.is_public).exists():
            self.file.delete(False)

    def delete(self, *args, **kwargs):
        super().delete_restorable(*args, **kwargs)
    delete.alters_data = True

    def _set_valid_name_for_restore(self):
        """
        Generates the first available name for restore.
        """
        basename, extension = os.path.splitext(self.clean_actual_name)
        if self.folder:
            files = self.folder.files
        else:
            try:
                owner = self.owner
            except auth_models.User.DoesNotExist:
                owner = None
            if owner:
                files = filer.models.tools.get_user_clipboard(self.owner).files.all()
            else:
                from filer.models.virtualitems import UnfiledImages
                files = UnfiledImages().files
        existing_file_names = [f.clean_actual_name for f in files]
        i = 1
        while self.clean_actual_name in existing_file_names:
            filename = "%s_%s%s" % (basename, i, extension)
            if self.name in ('', None):
                self.original_filename = filename
            else:
                self.name = filename
            i += 1

    def restore(self):
        """
        Restores the file to its folder location.
        """
        if self.folder_id:
            Folder = filer.models.foldermodels.Folder
            try:
                self.folder
            except Folder.DoesNotExist:
                self.folder = Folder.trash.get(id=self.folder_id)

            self.folder.restore_path()
            self.folder = filer.models.Folder.objects.get(id=self.folder_id)

        old_location, new_location = self.file.name, None
        self._set_valid_name_for_restore()
        destination = self.file.field.upload_to(self, self.upload_to_name)
        try:
            new_location = self._copy_file(destination)
        except Exception as e:
            silence_error_if_missing_file(e)
            if filer_settings.FILER_ENABLE_LOGGING:
                logger.error('Error while trying to copy file: %s to %s.' % (
                    old_location, destination), e)
        else:
            self.file.delete(False)
        finally:
            new_location = new_location or destination
            File.trash.filter(pk=self.pk).update(
                deleted_at=None, file=new_location,
                name=self.name, original_filename=self.original_filename)
            self.deleted_at = None
            self.file.name = new_location
            if self.owner_id and not self.folder_id:
                try:
                    clipboard = filer.models.tools.get_user_clipboard(self.owner)
                    clipboard.append_file(File.objects.get(id=self.id))
                except auth_models.User.DoesNotExist:
                    pass
        # Invalidate cache for the folder this file was restored to
        invalidate_folder_listing_cache_for_file(self)

    def __str__(self):
        try:
            name = self.pretty_logical_path
        except:
            name = self.actual_name
        return name

    @property
    def label(self):
        if self.name in ['', None]:
            text = self.original_filename or 'unnamed file'
        else:
            text = self.name
        return f"{text}"

    def _cmp(self, a, b):
        return (a > b) - (a < b)

    def __lt__(self, other):
        return self._cmp(self.label.lower(), other.label.lower()) < 0

    # PBS-specific: hash-based actual_name
    @property
    def actual_name(self):
        if not self.sha1:
            try:
                self.generate_sha1()
            except (IOError, TypeError, ValueError):
                return self.clean_actual_name
        try:
            folder = self.folder.get_ancestors().first()
            root_folder = getattr(folder, 'name', None)
        except:
            root_folder = None
        if root_folder in filer_settings.FILER_NOHASH_ROOTFOLDERS:
            name_fmt = '{actual_name}'
        else:
            name_fmt = '{hashcode}_{actual_name}'
        name = name_fmt.format(hashcode=self.sha1[:10],
                               actual_name=self.clean_actual_name)
        return name

    @property
    def upload_to_name(self):
        """
        For normal files this is the actual name with the hash but clipboard
        file upload locations are the clean names.
        """
        if self.folder:
            return self.actual_name
        else:
            return self.clean_actual_name

    @property
    def clean_actual_name(self):
        """The name displayed to the user."""
        if self.name in ('', None):
            name = "%s" % (self.original_filename,)
        else:
            name = "%s" % (self.name,)
        return name

    @property
    def pretty_logical_path(self):
        its_dir = self.logical_folder
        if its_dir.is_root:
            directory_path = ''
        else:
            directory_path = its_dir.pretty_logical_path
        full_path = '{}{}{}'.format(directory_path, os.sep, self.actual_name)
        return full_path

    # Upstream: permission methods
    def has_edit_permission(self, request):
        return request.user.has_perm("filer.change_file") and self.has_generic_permission(request, 'edit')

    def has_read_permission(self, request):
        return self.has_generic_permission(request, 'read')

    def has_add_children_permission(self, request):
        return request.user.has_perm("filer.add_file") and self.has_generic_permission(request, 'add_children')

    def has_generic_permission(self, request, permission_type):
        user = request.user
        if not user.is_authenticated:
            return False
        elif user.is_superuser:
            return True
        elif user == self.owner:
            return True
        elif self.folder:
            return self.folder.has_generic_permission(request, permission_type)
        else:
            return False

    def get_admin_url(self, action):
        return reverse(
            'admin:{}_{}_{}'.format(
                self._meta.app_label,
                self._meta.model_name,
                action
            ),
            args=(self.pk,)
        )

    def get_admin_url_path(self):
        return self.get_admin_url("change")

    def get_admin_change_url(self):
        return self.get_admin_url("change")

    def get_admin_expand_view_url(self):
        return self.get_admin_url("expand")

    def get_admin_delete_url(self):
        return self.get_admin_url("delete")

    @property
    def url(self):
        """
        to make the model behave like a file field
        """
        if self.is_in_trash():
            return ''
        try:
            r = self.file.url
        except:  # noqa
            r = ''
        from filer.utils.cdn import get_cdn_url
        return get_cdn_url(self, r)

    @property
    def canonical_time(self):
        if settings.USE_TZ:
            return int((self.uploaded_at - datetime(1970, 1, 1, 1, tzinfo=timezone.utc)).total_seconds())
        else:
            return int((self.uploaded_at - datetime(1970, 1, 1, 1)).total_seconds())

    @property
    def canonical_url(self):
        url = ''
        if self.file and self.is_public:
            try:
                url = reverse('canonical', kwargs={
                    'uploaded_at': self.canonical_time,
                    'file_id': self.id
                })
            except NoReverseMatch:
                pass
        return url

    @property
    def path(self):
        try:
            return self.file.path
        except:  # noqa
            return ""

    @property
    def size(self):
        return self._file_size or 0

    @property
    def extension(self):
        filetype = os.path.splitext(self.file.name)[1].lower()
        if len(filetype) > 0:
            filetype = filetype[1:]
        return filetype

    @property
    def logical_folder(self):
        if not self.folder:
            from filer.models.virtualitems import UnfiledImages
            return UnfiledImages()
        else:
            return self.folder

    @property
    def logical_path(self):
        folder_path = []
        if self.folder:
            folder_path.extend(self.folder.get_ancestors())
        folder_path.append(self.logical_folder)
        return folder_path

    @property
    def duplicates(self):
        return list(File.objects.find_duplicates(self))

    # PBS-specific: site/core permission methods
    def is_core(self):
        if self.folder:
            return self.folder.is_core()
        return False

    def is_readonly_for_user(self, user):
        if self.folder:
            return self.folder.is_readonly_for_user(user)
        return False

    def is_restricted_for_user(self, user):
        perm = 'filer.can_restrict_operations'
        return (self.restricted and (
            not (user.has_perm(perm, self) or user.has_perm(perm)) or
            not can_restrict_on_site(user, self.folder.site)))

    def can_change_restricted(self, user):
        perm = 'filer.can_restrict_operations'
        if not user.has_perm(perm, self) and not user.has_perm(perm):
            return False
        if not self.folder:
            return False
        if not can_restrict_on_site(user, self.folder.site):
            return False
        if self.folder.restricted == self.restricted == True:
            return False
        if self.folder.restricted == self.restricted == False:
            return True
        if self.folder.restricted == True and self.restricted == False:
            raise IntegrityError(
                'Re-save folder %s to fix restricted property' % (
                    self.folder.pretty_logical_path))
        return True

    def has_change_permission(self, user):
        if not self.folder:
            return True
        if self.is_readonly_for_user(user):
            return True
        if not self.folder.site and has_admin_role(user):
            return True
        if self.folder.site:
            can_change_file = (user.has_perm('filer.change_file', self) or
                               user.has_perm('filer.change_file'))
            return can_change_file and has_role_on_site(user, self.folder.site)
        return False

    def has_delete_permission(self, user):
        if not self.folder:
            return True
        if self.is_readonly_for_user(user):
            return False
        if not self.folder.site and has_admin_role(user):
            return True
        if self.folder.site:
            can_delete_file = (user.has_perm('filer.delete_file', self) or
                               user.has_perm('filer.delete_file'))
            return can_delete_file and has_role_on_site(user, self.folder.site)
        return False
