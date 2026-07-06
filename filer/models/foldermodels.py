import itertools
import logging

from django.conf import settings
from django.contrib.auth import models as auth_models
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.db import models, IntegrityError, transaction
from django.db.models import Q, query, signals, DEFERRED
from django.dispatch import receiver
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from urllib.parse import quote

import mptt

from .. import settings as filer_settings
from ..cache import get_folder_permission_cache, update_folder_permission_cache
from ..utils.cache import invalidate_folder_listing_cache
from ..utils.cms_roles import (
    get_sites_for_user,
    get_sites_without_restriction_perm,
    has_admin_role,
    has_admin_role_on_site,
    has_role_on_site,
    can_restrict_on_site,
)
from . import mixins

import filer


logger = logging.getLogger(__name__)


class FolderPermissionManager(models.Manager):
    """
    These methods are called by introspection from "has_generic_permission" on
    the folder model.
    """
    def get_read_id_list(self, user):
        return self.__get_id_list(user, "can_read")

    def get_edit_id_list(self, user):
        return self.__get_id_list(user, "can_edit")

    def get_add_children_id_list(self, user):
        return self.__get_id_list(user, "can_add_children")

    def __get_id_list(self, user, attr):
        if user.is_superuser or not filer_settings.FILER_ENABLE_PERMISSIONS:
            return 'All'
        cached_id_list = get_folder_permission_cache(user, attr)
        if cached_id_list:
            return cached_id_list

        allow_list = set()
        deny_list = set()
        group_ids = user.groups.all().values_list('id', flat=True)
        q = Q(user=user) | Q(group__in=group_ids) | Q(everybody=True)
        perms = self.filter(q)

        for perm in perms:
            p = getattr(perm, attr)

            if p is None:
                continue

            if not perm.folder:
                assert perm.type == FolderPermission.ALL

                if p == FolderPermission.ALLOW:
                    allow_list.update(Folder.objects.all().values_list('id', flat=True))
                else:
                    deny_list.update(Folder.objects.all().values_list('id', flat=True))
                continue

            folder_id = perm.folder.id

            if p == FolderPermission.ALLOW:
                allow_list.add(folder_id)
            else:
                deny_list.add(folder_id)

            if perm.type in [FolderPermission.ALL, FolderPermission.CHILDREN]:
                if p == FolderPermission.ALLOW:
                    allow_list.update(perm.folder.get_descendants_ids())
                else:
                    deny_list.update(perm.folder.get_descendants_ids())

        id_list = allow_list - deny_list
        update_folder_permission_cache(user, attr, id_list)
        return id_list


# PBS-specific: chainable queryset mixin with trash/restriction support
class FoldersChainableQuerySetMixin:

    def with_bad_metadata(self):
        return self.filter(has_all_mandatory_data=False)

    def valid_destinations(self, user):
        available_sites = get_sites_for_user(user)
        core_folders = Q(folder_type=Folder.CORE_FOLDER)
        no_site = Q(site__isnull=True)
        shared_folders = ~Q(site__in=available_sites)
        return self.exclude(core_folders | no_site | shared_folders)

    def readonly(self, user):
        core_folders = Q(folder_type=Folder.CORE_FOLDER)
        available_sites = get_sites_for_user(user)
        shared_folders = Q(~Q(site__in=available_sites) &
                           Q(shared__in=available_sites))
        readonly_folders = Q(core_folders | shared_folders)
        return self.filter(readonly_folders)

    def restricted_descendants(self, user):
        sites = get_sites_without_restriction_perm(user)
        if not sites:
            return self.none()
        descendant_filter = None
        for node in self:
            q = Q(**{
                'tree_id': node.tree_id,
                'lft__gt': node.lft - 1,
                'rght__lt': node.rght + 1,
            })
            if descendant_filter is None:
                descendant_filter = q
            else:
                descendant_filter |= q
        if not descendant_filter:
            return self.none()
        restr_q = Q(Q(restricted=True) | Q(
                        Q(all_files__restricted=True) &
                        Q(all_files__deleted_at__isnull=True)))
        restr_q &= Q(site__in=sites)
        return self.model.objects.filter(
            descendant_filter).filter(restr_q).distinct()

    def unrestricted(self, user):
        sites = get_sites_without_restriction_perm(user)
        if not sites:
            return self
        return self.exclude(restricted=True, site__in=sites)

    def in_trash(self):
        return self.filter(deleted_at__isnull=False)

    def alive(self):
        return self.filter(deleted_at__isnull=True)


class FolderQueryset(query.QuerySet, FoldersChainableQuerySetMixin):
    pass


class FolderManager(models.Manager):

    def get_queryset(self):
        return FolderQueryset(self.model, using=self._db)

    def __getattr__(self, name):
        if name.startswith('__'):
            return super(FolderManager, self).__getattr__(self, name)
        return getattr(self.get_queryset(), name)


class AliveFolderManager(FolderManager):
    def get_queryset(self):
        return FolderQueryset(self.model, using=self._db).alive()


class TrashFolderManager(FolderManager):
    def get_queryset(self):
        return FolderQueryset(self.model, using=self._db).in_trash()


@mixins.trashable
class Folder(models.Model, mixins.IconsMixin):
    """
    Represents a Folder that things (files) can be put into. Folders are *NOT*
    mirrored in the Filesystem and can have any unicode chars as their name.
    Other models may attach to a folder with a ForeignKey. If the related name
    ends with "_files" they will automatically be listed in the
    folder.files list along with all the other models that link to the folder
    in this way. Make sure the linked models obey the AbstractFile interface
    (Duck Type).
    """
    file_type = 'Folder'
    is_root = False
    can_have_subfolders = True
    _icon = 'plainfolder'

    # PBS-specific: folder types
    SITE_FOLDER = 0
    CORE_FOLDER = 1

    FOLDER_TYPES = {
        SITE_FOLDER: 'Site Folder',
        CORE_FOLDER: 'Core Folder',
    }

    parent = models.ForeignKey(
        'self',
        verbose_name=_('parent'),
        null=True,
        blank=True,
        related_name='children',
        on_delete=models.CASCADE,
    )

    name = models.CharField(
        _('name'),
        max_length=255,
    )

    owner = models.ForeignKey(
        getattr(settings, 'AUTH_USER_MODEL', 'auth.User'),
        verbose_name=_('owner'),
        related_name='filer_owned_folders',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    uploaded_at = models.DateTimeField(
        _('uploaded at'),
        auto_now_add=True,
    )

    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True,
    )

    modified_at = models.DateTimeField(
        _('modified at'),
        auto_now=True,
    )

    # PBS-specific fields
    folder_type = models.IntegerField(
        choices=list(FOLDER_TYPES.items()),
        default=SITE_FOLDER,
    )

    site = models.ForeignKey(
        Site,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text=_("Select the site which will use this folder."),
    )

    restricted = models.BooleanField(
        _("Restrict Editors and Writers from being able to edit "
          "or delete anything from this folder"),
        default=False,
        help_text=_('If this box is checked, '
                    'Editors and Writers will still be able to '
                    'view this folder assets, add them to a plugin or smart '
                    'snippet but will not be able to delete or '
                    'modify the current version of the assets.'),
    )

    shared = models.ManyToManyField(
        Site,
        blank=True,
        related_name='shared',
        verbose_name=_("Share folder with sites"),
        help_text=_("All the sites which you share this folder with will "
                    "be able to use this folder on their pages, with all of "
                    "its assets. However, they will not be able to change, "
                    "delete or move it, not even add new assets."),
    )

    # PBS-specific: trash managers
    objects = AliveFolderManager()
    trash = TrashFolderManager()
    all_objects = FolderManager()

    class Meta:
        ordering = ('name',)
        permissions = (
            ("can_use_directory_listing", "Can use directory listing"),
            ("can_restrict_operations", "Can restrict files or folders"),
        )
        app_label = 'filer'
        verbose_name = _("Folder")
        verbose_name_plural = _("Folders")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.__dict__.get('name', DEFERRED) is not DEFERRED:
            self._old_name = self.name
        if self.__dict__.get('parent_id', DEFERRED) is not DEFERRED:
            self._old_parent_id = self.parent_id

    def __str__(self):
        try:
            name = self.pretty_logical_path
        except:
            name = self.name
        return name

    def __repr__(self):
        return f'<{self.__class__.__name__}(pk={self.pk}): {self.name}>'

    def clean(self):
        if self.name == filer.models.clipboardmodels.Clipboard.folder_name:
            raise ValidationError(
                _('%s is reserved for internal use. '
                  'Please choose a different name') % self.name)

        if self.name and "/" in self.name:
            raise ValidationError("Slashes are not allowed in folder names.")

        duplicate_folders_q = Folder.objects.filter(
            parent=self.parent_id,
            name=self.name)
        if self.pk:
            duplicate_folders_q = duplicate_folders_q.exclude(pk=self.pk)

        if duplicate_folders_q.exists():
            raise ValidationError(
                'This folder name is already in use. '
                'Please choose a different name.')

        if not self.parent:
            if (self.folder_type == Folder.SITE_FOLDER and
                    not self.site):
                raise ValidationError('Folder is a Site folder. '
                                      'Site is required.')
            if (self.folder_type == Folder.CORE_FOLDER and not self.parent and
                    self.site):
                raise ValidationError('Folder is a Core folder. '
                                      'Site must be empty.')

    def set_metadata_from_parent(self):
        if self.parent:
            self.site = self.parent.site
            self.folder_type = self.parent.folder_type
            if self.parent.restricted:
                self.restricted = self.parent.restricted

        if self.is_core():
            self.site = None

        self._update_descendants = self.has_new_metadata_value()

    def has_new_metadata_value(self):
        if not self.pk:
            return True
        metadata_fields = ['restricted', 'site_id', 'folder_type']
        old_metadata = self.__class__.all_objects.\
                 filter(pk=self.pk).values(*metadata_fields).get()
        for field in metadata_fields:
            if getattr(self, field) != old_metadata[field]:
                return True
        return False

    def is_affecting_file_paths(self):
        return (self._old_name != self.name or
                self._old_parent_id != getattr(self, 'parent_id', None))

    def update_descendants_metadata(self):
        descendants = None
        if self._update_descendants:
            descendants = self.get_descendants()
            descendants.update(
                folder_type=self.folder_type, site=self.site,
                restricted=self.restricted)
            desc_ids = [desc.pk for desc in descendants]
            if self.pk:
                desc_ids.append(self.pk)
            file_mgr = filer.models.filemodels.File.all_objects
            file_mgr.filter(
                folder__in=desc_ids).update(restricted=self.restricted)

        if self.parent:
            parent_shared_sites = self.parent.shared.values_list(
                'id', flat=True)
            instance_shared_sites = self.shared.values_list('id', flat=True)
            if set(instance_shared_sites) != set(parent_shared_sites):
                shared_sites = self.parent.shared.all()
                self.shared.set(shared_sites)
                descendants = descendants or self.get_descendants()
                for desc_folder in descendants:
                    desc_folder.shared.set(shared_sites)

    def save(self, *args, **kwargs):
        if not filer_settings.FOLDER_AFFECTS_URL:
            self.set_metadata_from_parent()
            super().save(*args, **kwargs)
            self.update_descendants_metadata()
            invalidate_folder_listing_cache(self)
            return

        storages = []
        old_locations = []
        new_locations = []

        def delete_from_locations(locations, storages):
            for location, storage in zip(locations, storages):
                storage.delete(location)

        try:
            with transaction.atomic(savepoint=False):
                self.set_metadata_from_parent()
                super().save(*args, **kwargs)
                self.update_descendants_metadata()
                if self.is_affecting_file_paths():
                    desc_ids = list(self.get_descendants(
                        include_self=True).values_list('id', flat=True))
                    file_mgr = filer.models.filemodels.File.objects
                    all_files = file_mgr.filter(folder__in=desc_ids)
                    for f in all_files:
                        old_location = f.file.name
                        new_location = f.update_location_on_storage()
                        if old_location != new_location:
                            storages.append(f.file.storage)
                            old_locations.append(old_location)
                            new_locations.append(new_location)
        except:
            delete_from_locations(new_locations, storages)
            raise
        else:
            delete_from_locations(old_locations, storages)
        invalidate_folder_listing_cache(self)

    # PBS-specific: trash methods
    def soft_delete(self):
        deletion_time = timezone.now()
        desc_ids = list(self.get_descendants(
            include_self=True).values_list('id', flat=True))
        file_mgr = filer.models.filemodels.File.objects
        files_qs = file_mgr.filter(folder__in=desc_ids)
        for filer_file in files_qs:
            filer_file.soft_delete(deletion_time=deletion_time)
        Folder.objects.filter(
            id__in=desc_ids).update(deleted_at=deletion_time)
        self.deleted_at = deletion_time
        # Invalidate cache for this folder and its parent
        invalidate_folder_listing_cache(self)

    def hard_delete(self):
        desc_ids = list(self.get_descendants(
            include_self=True).values_list('id', flat=True))
        file_mgr = filer.models.filemodels.File.all_objects
        for file_obj in file_mgr.filter(folder__in=desc_ids):
            file_obj.hard_delete()
        super().delete()

    def delete(self, *args, **kwargs):
        super().delete_restorable(*args, **kwargs)
    delete.alters_data = True

    def _generate_valid_name_for_restore(self):
        name = self.name
        i = 1
        while self.get_siblings().filter(
                deleted_at__isnull=True, name=name).exists():
            name = "%s_%s" % (self.name, i)
            i += 1
        return name

    def restore_path(self):
        trashed_ancestors = self.get_ancestors(include_self=True).filter(
            deleted_at__isnull=False)
        first_node_trashed = trashed_ancestors[:1]
        if first_node_trashed:
            first_node_trashed = first_node_trashed[0]
            new_name = first_node_trashed._generate_valid_name_for_restore()
            if new_name != first_node_trashed.name:
                Folder.trash.filter(
                    id=first_node_trashed.id).update(name=new_name)
            trashed_ancestors.update(deleted_at=None)

    def restore(self):
        self.restore_path()
        desc_ids = [self.id]
        descendants = self.get_descendants(include_self=True).filter(
            deleted_at__isnull=False)
        for descendant in descendants:
            new_name = descendant._generate_valid_name_for_restore()
            Folder.trash.filter(id=descendant.id).update(
                deleted_at=None, name=new_name)
            desc_ids.append(descendant.id)
        file_mgr = filer.models.filemodels.File.trash
        files_qs = file_mgr.filter(folder__in=desc_ids)
        for filer_file in files_qs:
            filer_file.restore()
        self.deleted_at = None
        # Invalidate cache for this folder and its parent
        invalidate_folder_listing_cache(self)

    @property
    def trashed_file_count(self):
        file_mgr = filer.models.filemodels.File.trash
        return file_mgr.filter(folder_id=self.id).count()

    @property
    def trashed_children_count(self):
        return Folder.trash.filter(parent_id=self.id).count()

    @property
    def file_count(self):
        if not hasattr(self, '_file_count_cache'):
            self._file_count_cache = self.files.count()
        return self._file_count_cache

    @property
    def children_count(self):
        if not hasattr(self, '_children_count_cache'):
            self._children_count_cache = self.children.count()
        return self._children_count_cache

    @property
    def item_count(self):
        return self.file_count + self.children_count

    @property
    def trashed_files(self):
        trash_file_mgr = filer.models.filemodels.File.trash
        if not self.pk:
            return trash_file_mgr.none()
        return trash_file_mgr.filter(folder=self).order_by(
            'title', 'name', 'original_filename')

    @property
    def files(self):
        return filer.models.File.objects.filter(folder=self)

    def entries_with_names(self, names):
        q = Q(name__in=names)
        q |= Q(original_filename__in=names) & (Q(name__isnull=True) | Q(name=''))
        files_with_names = filer.models.File.objects.filter(
            folder=self).filter(q)
        folders_with_names = Folder.objects.filter(
            parent=self, name__in=names)
        return list(itertools.chain(files_with_names, folders_with_names))

    def pretty_path_entries(self):
        subdirs = self.get_descendants(include_self=True).filter(
            deleted_at__isnull=True)
        subdir_files = filer.models.File.objects.filter(folder__in=subdirs)
        file_paths = [x.pretty_logical_path for x in subdir_files]
        dir_paths = [x.pretty_logical_path for x in subdirs]
        return file_paths + dir_paths

    def get_descendants_ids(self):
        desc = []
        for child in self.children.all():
            desc.append(child.id)
            desc.extend(child.get_descendants_ids())
        return desc

    @property
    def logical_path(self):
        folder_path = []
        try:
            if self.parent:
                folder_path.extend(self.parent.get_ancestors(
                    include_self=True).filter(deleted_at__isnull=True))
        except Folder.DoesNotExist:
            pass
        return folder_path

    @property
    def pretty_logical_path(self):
        return "/%s" % "/".join([f.name
                                   for f in self.logical_path + [self]])

    @property
    def quoted_logical_path(self):
        return quote(self.pretty_logical_path)

    # Upstream permission methods
    def has_edit_permission(self, request):
        return request.user.has_perm("filer.change_folder") and self.has_generic_permission(request, 'edit')

    def has_read_permission(self, request):
        return self.has_generic_permission(request, 'read')

    def has_add_children_permission(self, request):
        return request.user.has_perm("filer.change_folder") and self.has_generic_permission(request, 'add_children')

    def has_generic_permission(self, request, permission_type):
        user = request.user
        if not user.is_authenticated:
            return False
        elif user.is_superuser:
            return True
        elif user == self.owner:
            return True
        else:
            if not hasattr(self, "permission_cache") or\
               permission_type not in self.permission_cache or \
               request.user.pk != self.permission_cache['user'].pk:
                if not hasattr(self, "permission_cache") or request.user.pk != self.permission_cache['user'].pk:
                    self.permission_cache = {
                        'user': request.user,
                    }
                func = getattr(FolderPermission.objects,
                               "get_%s_id_list" % permission_type)
                permission = func(user)
                if permission == "All":
                    self.permission_cache[permission_type] = True
                    self.permission_cache['read'] = True
                    self.permission_cache['edit'] = True
                    self.permission_cache['add_children'] = True
                else:
                    self.permission_cache[permission_type] = self.id in permission
            return self.permission_cache[permission_type]

    def get_admin_change_url(self):
        return reverse('admin:filer_folder_change', args=(self.id,))

    def get_admin_url_path(self):
        return reverse('admin:filer_folder_change', args=(self.id,))

    def get_admin_directory_listing_url_path(self):
        return reverse('admin:filer-directory_listing', args=(self.id,))

    def get_admin_delete_url(self):
        return reverse(
            f'admin:{self._meta.app_label}_{self._meta.model_name}_delete',
            args=(self.pk,)
        )

    def contains_folder(self, folder_name):
        try:
            self.children.get(name=folder_name)
            return True
        except Folder.DoesNotExist:
            return False

    @property
    def actual_name(self):
        return self.name

    @property
    def get_folder_type_display(self):
        if self.shared.exists():
            return 'Shared by site'
        return Folder.FOLDER_TYPES[self.folder_type]

    # PBS-specific: site/core permission methods
    def is_core(self):
        return self.folder_type == Folder.CORE_FOLDER

    def is_readonly_for_user(self, user):
        return self.is_core() or (
            self.site and not has_role_on_site(user, self.site) and
            self.shared.filter(id__in=get_sites_for_user(user)).exists())

    def is_restricted_for_user(self, user):
        perm = 'filer.can_restrict_operations'
        return (self.restricted and (
            not (user.has_perm(perm, self) or user.has_perm(perm)) or
            not can_restrict_on_site(user, self.site)))

    def can_change_restricted(self, user):
        perm = 'filer.can_restrict_operations'
        if (not (user.has_perm(perm, self) or user.has_perm(perm)) or
                not can_restrict_on_site(user, self.site)):
            return False
        if not self.parent:
            return True
        if self.parent.restricted == self.restricted == True:
            return False
        if self.parent.restricted == self.restricted == False:
            return True
        if self.parent.restricted == True and self.restricted == False:
            raise IntegrityError(
                'Re-save folder %s to fix restricted property' % (
                    self.parent.pretty_logical_path))
        return True

    def has_add_permission(self, user):
        if (self.is_readonly_for_user(user) or
                self.is_restricted_for_user(user)):
            return False
        if not self.site and has_admin_role(user):
            return True
        if not self.site or not has_role_on_site(user, self.site):
            return False
        perm = 'filer.add_folder'
        return user.has_perm(perm, self.site) or user.has_perm(perm)

    def has_change_permission(self, user):
        if (self.is_readonly_for_user(user) or
                self.is_restricted_for_user(user)):
            return False
        if not self.site and has_admin_role(user):
            return True
        if not self.site:
            return False
        if not self.parent:
            return has_admin_role_on_site(user, self.site)
        perm = 'filer.change_folder'
        return ((user.has_perm(perm, self.site) or user.has_perm(perm)) and
                has_role_on_site(user, self.site))

    def has_delete_permission(self, user):
        if (self.is_readonly_for_user(user) or
                self.is_restricted_for_user(user)):
            return False
        if not self.site and user.is_superuser:
            return True
        if not self.site:
            return False
        if not self.parent:
            return has_admin_role_on_site(user, self.site)
        perm = 'filer.delete_folder'
        return ((user.has_perm(perm, self.site) or user.has_perm(perm)) and
                has_role_on_site(user, self.site))


# MPTT registration
try:
    mptt.register(Folder)
except mptt.AlreadyRegistered:
    pass


@receiver(signals.m2m_changed, sender=Folder.shared.through)
def update_shared_sites_for_descendants(instance, **kwargs):
    """
    Makes sure that folders keep all shared sites from their root folder.
    """
    action = kwargs['action']
    if not action.startswith('post_') or instance.parent_id:
        return

    instance = Folder.all_objects.get(id=instance.id)
    sites = instance.shared.all()
    descendants = instance.get_descendants()
    for desc_folder in descendants:
        desc_folder.shared.set(sites)


# Upstream: FolderPermission model
class FolderPermission(models.Model):
    ALL = 0
    THIS = 1
    CHILDREN = 2

    ALLOW = 1
    DENY = 0

    TYPES = [
        (ALL, _("all items")),
        (THIS, _("this item only")),
        (CHILDREN, _("this item and all children")),
    ]

    PERMISIONS = [
        (None, _("inherit")),
        (ALLOW, _("allow")),
        (DENY, _("deny")),
    ]

    folder = models.ForeignKey(
        Folder,
        verbose_name=("folder"),
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )

    type = models.SmallIntegerField(
        _("type"),
        choices=TYPES,
        default=ALL,
    )

    user = models.ForeignKey(
        getattr(settings, 'AUTH_USER_MODEL', 'auth.User'),
        related_name="filer_folder_permissions",
        on_delete=models.SET_NULL,
        verbose_name=_("user"),
        blank=True,
        null=True,
    )

    group = models.ForeignKey(
        auth_models.Group,
        related_name="filer_folder_permissions",
        verbose_name=_("group"),
        blank=True,
        null=True,
        on_delete=models.CASCADE,
    )

    everybody = models.BooleanField(
        _("everybody"),
        default=False,
    )

    can_read = models.SmallIntegerField(
        _("can read"),
        choices=PERMISIONS,
        blank=True,
        null=True,
        default=None,
    )

    can_edit = models.SmallIntegerField(
        _("can edit"),
        choices=PERMISIONS,
        blank=True,
        null=True,
        default=None,
    )

    can_add_children = models.SmallIntegerField(
        _("can add children"),
        choices=PERMISIONS,
        blank=True,
        null=True,
        default=None,
    )

    class Meta:
        verbose_name = _('folder permission')
        verbose_name_plural = _('folder permissions')
        app_label = 'filer'

    objects = FolderPermissionManager()

    def __str__(self):
        return self.pretty_logical_path

    def __repr__(self):
        return f'<{self.__class__.__name__}(pk={self.pk}): folder="{self.pretty_logical_path}">'

    def clean(self):
        if self.type == self.ALL and self.folder:
            raise ValidationError(_('Folder cannot be selected with type "all items".'))
        if self.type != self.ALL and not self.folder:
            raise ValidationError(_('Folder has to be selected when type is not "all items".'))
        if self.everybody and (self.user or self.group):
            raise ValidationError(_('User or group cannot be selected together with "everybody".'))
        if not self.user and not self.group and not self.everybody:
            raise ValidationError(_('At least one of user, group, or "everybody" has to be selected.'))

    @cached_property
    def pretty_logical_path(self):
        if self.folder:
            return self.folder.pretty_logical_path
        return gettext("All Folders")

    pretty_logical_path.short_description = _("Logical Path")

    @cached_property
    def who(self):
        parts = []
        if self.user:
            parts.append(_("User: {user}").format(user=self.user))
        if self.group:
            parts.append(_("Group: {group}").format(group=self.group))
        if self.everybody:
            parts.append(_("Everybody"))
        if parts:
            return format_html_join("; ", '{}', ((p,) for p in parts))
        return '–'

    who.short_description = _("Who")

    @cached_property
    def what(self):
        mapping = {
            'can_edit': _("Edit"),
            'can_read': _("Read"),
            'can_add_children': _("Add children"),
        }
        perms = []
        for key, text in mapping.items():
            perm = getattr(self, key)
            if perm == self.ALLOW:
                perms.append(text)
            elif perm == self.DENY:
                perms.append('\u0336'.join(text) + '\u0336')
        return format_html_join(", ", '{}', ((p,) for p in perms))

    what.short_description = _("What")
