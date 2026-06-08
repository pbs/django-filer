from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .. import settings as filer_settings
from ..utils.cms_roles import has_admin_role
from . import mixins
from .filemodels import File
from .foldermodels import Folder


class DummyFolder(mixins.IconsMixin):
    file_type = 'DummyFolder'
    name = "Dummy Folder"
    is_root = True
    is_smart_folder = True
    can_have_subfolders = False
    parent = None
    pk = None
    id = None
    _icon = "plainfolder"

    @property
    def virtual_folders(self):
        return []

    @property
    def children(self):
        return Folder.objects.none()

    @property
    def files(self):
        return File.objects.none()
    parent_url = None

    @property
    def image_files(self):
        return self.files

    @property
    def logical_path(self):
        """
        Gets logical path of the folder in the tree structure.
        Used to generate breadcrumbs
        """
        return []


class UnfiledImages(DummyFolder):
    """PBS name for unsorted/unfiled images."""
    name = _("unfiled files")
    is_root = True
    is_unsorted_uploads = True
    _icon = "unfiled_folder"

    def __init__(self, user=None):
        super().__init__()
        self.user = user

    def _files(self):
        return File.objects.filter(
            folder__isnull=True, clipboarditem__isnull=True)
    files = property(_files)

    def get_admin_directory_listing_url_path(self):
        return reverse('admin:filer-directory_listing-unfiled_images')


# Upstream compat alias
UnsortedImages = UnfiledImages


class ImagesWithMissingData(DummyFolder):
    name = _("files with missing metadata")
    is_root = True
    _icon = "incomplete_metadata_folder"

    @property
    def files(self):
        return File.objects.filter(has_all_mandatory_data=False)

    def get_admin_directory_listing_url_path(self):
        return reverse('admin:filer-directory_listing-images_with_missing_data')


class FolderRoot(DummyFolder):
    name = _('root')
    is_root = True
    is_smart_folder = False
    can_have_subfolders = True
    restricted = False

    @property
    def virtual_folders(self):
        return [UnfiledImages()]

    @property
    def children(self):
        return Folder.objects.filter(parent__isnull=True)
    parent_url = None

    def contains_folder(self, folder_name):
        try:
            self.children.get(name=folder_name)
            return True
        except Folder.DoesNotExist:
            return False

    def entries_with_names(self, names):
        return self.children.filter(name__in=names)

    def get_admin_directory_listing_url_path(self):
        return reverse('admin:filer-directory_listing-root')

    # PBS-specific permission methods
    def is_restricted_for_user(self, user):
        return not has_admin_role(user)

    def can_change_restricted(self, user):
        return has_admin_role(user)

    def is_readonly_for_user(self, user):
        return not has_admin_role(user)
