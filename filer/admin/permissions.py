#-*- coding: utf-8 -*-
from django.contrib import admin
from django.core.urlresolvers import reverse, resolve
from filer.models import Folder
from filer.admin.tools import (has_admin_role, has_role_on_site,
                               has_admin_role_on_site,
                               get_admin_sites_for_user,
                               get_sites_for_user,)

class CommonModelAdmin(admin.ModelAdmin):

    def _get_post_url(self, obj):
        """
        Needed to retrieve the changelist url as Folder/File can be extended
            and admin url may change
        """
        # Code borrowed from django ModelAdmin to determine
        #      changelist on the fly
        opts = obj._meta
        module_name = opts.module_name
        return reverse('admin:%s_%s_changelist' %
                       (opts.app_label, module_name),
            current_app=self.admin_site.name)


class FolderPermissionModelAdmin(CommonModelAdmin):

    def has_add_permission(self, request):
        # allow only make folder view
        current_view = resolve(request.path_info).url_name
        if not current_view == 'filer-directory_listing-make_root_folder':
            return False

        folder_id = request.REQUEST.get('parent_id', None)
        if not folder_id:
            # only site admins and superusers can add root folders
            if has_admin_role(request.user):
                return True
        else:
            folder = Folder.objects.get(id=folder_id)
            # nobody can add subfolders in core folders
            if folder.is_restricted():
                return False
            # only site admins can add subfolders in site folders with no site
            if not folder.site and has_admin_role(request.user):
                return True
            # regular users need to have permissions to add folders and
            #   need to have a role over the site owner of the folder
            can_add = super(CommonModelAdmin, self).\
                has_add_permission(request)
            if (folder.site and can_add
                    and has_role_on_site(request.user, folder.site)):
                return True
        return False

    def has_change_permission(self, request, obj=None):
        folder = obj
        can_change = super(CommonModelAdmin, self).\
            has_change_permission(request, folder)

        if not folder:
            return request.user.has_perm('filer.can_use_directory_listing')

        # nobody can change core folder
        if folder.is_restricted():
            return False
        # only admins can change site folders with no site owner
        if not folder.site and has_admin_role(request.user):
            return True

        if folder.site:
            if not folder.parent:
                # only site admins can change root site folders
                return has_admin_role_on_site(request.user, folder.site)
            return can_change and has_role_on_site(request.user, folder.site)

        return False

    def has_delete_permission(self, request, obj=None):
        folder = obj
        can_delete = super(CommonModelAdmin, self).\
            has_delete_permission(request, obj)

        if not folder:
            return can_delete

        if folder.is_restricted():
            return False

        # only admins can delete site folders with no site owner
        if not folder.site and has_admin_role(request.user):
            return True

        if folder.site:
            if not folder.parent:
                # only site admins can change root site folders
                return has_admin_role_on_site(request.user, folder.site)
            return can_delete and has_role_on_site(request.user, folder.site)

        return False

    def can_view_folder_content(self, request, folder):
        if folder.is_restricted():
            return True
        # only admins can see site folders with no site owner
        if not folder.site and has_admin_role(request.user):
            return True

        if folder.site and has_role_on_site(request.user, folder.site):
            return True

        return False

class FilePermissionModelAdmin(CommonModelAdmin):
    pass
