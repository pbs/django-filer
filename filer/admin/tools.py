from django.conf import settings as django_settings
from django.contrib.admin.options import IS_POPUP_VAR
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.utils.http import urlencode

from .. import settings
from ..utils.cms_roles import get_sites_for_user
from ..models.foldermodels import Folder


ALLOWED_PICK_TYPES = ('folder', 'file')


def check_files_edit_permissions(request, files):
    for f in files:
        if not f.has_edit_permission(request):
            raise PermissionDenied


def check_folder_edit_permissions(request, folders):
    for f in folders:
        if not f.has_edit_permission(request):
            raise PermissionDenied
        check_files_edit_permissions(request, f.files)
        check_folder_edit_permissions(request, f.children.all())


def check_files_read_permissions(request, files):
    for f in files:
        if not f.has_read_permission(request):
            raise PermissionDenied


def check_folder_read_permissions(request, folders):
    for f in folders:
        if not f.has_read_permission(request):
            raise PermissionDenied
        check_files_read_permissions(request, f.files)
        check_folder_read_permissions(request, f.children.all())


def userperms_for_request(item, request):
    r = []
    ps = ['read', 'edit', 'add_children']
    for p in ps:
        attr = "has_%s_permission" % p
        if hasattr(item, attr):
            x = getattr(item, attr)(request)
            if x:
                r.append(p)
    return r


def popup_status(request):
    return (
        IS_POPUP_VAR in request.GET
        or 'pop' in request.GET
        or IS_POPUP_VAR in request.POST
        or 'pop' in request.POST
    )


def popup_pick_type(request):
    pick_type = request.GET.get('_pick', request.POST.get('_pick'))
    if pick_type in ALLOWED_PICK_TYPES:
        return pick_type
    return None


def edit_from_widget(request):
    return request.GET.get('_edit_from_widget') == '1'


def get_directory_listing_type(request):
    list_type = request.GET.get('_list_type', None)
    if list_type not in settings.FILER_FOLDER_ADMIN_LIST_TYPE_CHOICES:
        return
    return list_type


def admin_url_params(request, params=None):
    params = params or {}
    if popup_status(request):
        params[IS_POPUP_VAR] = '1'
    pick_type = popup_pick_type(request)
    if pick_type:
        params['_pick'] = pick_type
    if edit_from_widget(request):
        params['_edit_from_widget'] = '1'
    list_type = get_directory_listing_type(request)
    if list_type and '_list_type' not in params.keys():
        params['_list_type'] = list_type
    return params


def admin_url_params_encoded(request, first_separator='?', params=None):
    params = urlencode(
        sorted(admin_url_params(request, params=params).items())
    )
    if not params:
        return ''
    return f'{first_separator}{params}'


class AdminContext(dict):
    def __init__(self, request):
        super().__init__()
        self.update(admin_url_params(request))

    def __missing__(self, key):
        if key == 'popup':
            return self.get(IS_POPUP_VAR, False) == '1'
        elif key == 'pick':
            return self.get('_pick', '')
        elif key.startswith('pick_'):
            return self.get('_pick', '') == key.split('pick_')[1]

    def __getattr__(self, name):
        if name in ('popup', 'pick') or name.startswith('pick_'):
            return self.get(name)
        raise AttributeError


# --- PBS-specific functions ---

def is_valid_destination(request, folder):
    user = request.user
    if folder.is_readonly_for_user(user):
        return False
    if not folder.site:
        return False
    if user.is_superuser:
        return True
    if folder.is_restricted_for_user(request.user):
        return False
    if folder.site.id in get_sites_for_user(user):
        return True
    return False


def _filter_available_sites(current_site, user):
    available_sites = get_sites_for_user(user)
    if current_site:
        current_site = float(current_site)
        if not user.is_superuser and current_site not in available_sites:
            available_sites = []
        else:
            available_sites = [current_site]
    return available_sites


def folders_available(current_site, user, folders_qs):
    """
    Returns a queryset with folders that current user can see.
    """
    available_sites = _filter_available_sites(current_site, user)
    if not available_sites:
        return folders_qs.none()

    core_folders = Q(folder_type=Folder.CORE_FOLDER)
    shared_folders = Q(shared__in=available_sites)
    accessible_site_folders = Q(site__in=available_sites)

    if user.is_superuser:
        # superusers can also see folders with no site assigned
        no_site_folders = Q(site__isnull=True) & ~core_folders
        visible = (core_folders | shared_folders |
                   accessible_site_folders | no_site_folders)
    else:
        visible = core_folders | shared_folders | accessible_site_folders

    return folders_qs.filter(visible).distinct()


def has_multi_file_action_permission(request, files, folders):
    """PBS: Check permissions for multi-file actions (move/copy/delete)."""
    from ..utils.cms_roles import (
        has_admin_role,
        get_admin_sites_for_user,
        get_sites_for_user,
    )
    # unfiled files can be moved/deleted so better to just exclude them
    files = files.exclude(folder__isnull=True)
    user = request.user

    if files.readonly(user).exists() or folders.readonly(user).exists():
        return False
    if user.is_superuser:
        return True

    if files.restricted(user).exists():
        return False

    if folders.restricted_descendants(user).exists():
        return False

    # only superusers can move/delete files/folders with no site ownership
    if (files.filter(folder__site__isnull=True).exists() or
            folders.filter(site__isnull=True).exists()):
        return False

    _exists_root_folders = folders.filter(parent__isnull=True).exists()
    if _exists_root_folders:
        if not has_admin_role(user):
            return False
        sites_allowed = [s.id for s in get_admin_sites_for_user(user)]
    else:
        sites_allowed = get_sites_for_user(user)

    if (files.exclude(folder__site__in=sites_allowed).exists() or
            folders.exclude(site__in=sites_allowed).exists()):
        return False

    return True
