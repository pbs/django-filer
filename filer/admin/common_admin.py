#-*- coding: utf-8 -*-
from django.contrib import admin
from django.contrib.admin.util import unquote
from django.core.urlresolvers import reverse, resolve
from django.http import HttpResponseRedirect
from filer.models import Folder
from filer.admin.tools import (has_admin_role, has_role_on_site,
                               has_admin_role_on_site,
                               get_admin_sites_for_user,
                               get_sites_for_user,)
from filer.views import (popup_param, selectfolder_param, popup_status,
                         selectfolder_status, current_site_param)

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

    def _get_parent_for_view(self, obj):
        return obj.parent

    def delete_view(self, request, object_id, extra_context=None):
        """
        Overrides the default to enable redirecting to the directory view after
        deletion of a image.

        we need to fetch the object and find out who the parent is
        before super, because super will delete the object and make it
        impossible to find out the parent folder to redirect to.
        """
        parent_folder = None
        try:
            obj = self.queryset(request).get(pk=unquote(object_id))
            parent_folder = self._get_parent_for_view(obj)
        except self.model.DoesNotExist:
            obj = None

        r = super(CommonModelAdmin, self).delete_view(
                    request=request, object_id=object_id,
                    extra_context=extra_context)

        url = r.get("Location", None)
        if (url in ["../../../../", "../../"] or
                url == self._get_post_url(obj)):
            if parent_folder:
                url = reverse('admin:filer-directory_listing',
                                  kwargs={'folder_id': parent_folder.id})
            else:
                url = reverse('admin:filer-directory_listing-root')
            url = "%s%s%s%s" % (url, popup_param(request),
                                selectfolder_param(request, "&"),
                                current_site_param(request),)

            return HttpResponseRedirect(url)
        return r

    def render_change_form(self, request, context, add=False, change=False,
                           form_url='', obj=None):
        extra_context = {'current_site': request.REQUEST.get(
                            'current_site', None),
                         'show_delete': True,
                         'is_popup': popup_status(request),
                         'select_folder': selectfolder_status(request), }
        context.update(extra_context)
        return super(CommonModelAdmin, self).render_change_form(
                        request=request, context=context, add=False,
                        change=False, form_url=form_url, obj=obj)

    def response_change(self, request, obj):
        """
        Overrides the default to be able to forward to the directory listing
        instead of the default change_list_view
        """
        r = super(CommonModelAdmin, self).response_change(request, obj)
        ## Code borrowed from django ModelAdmin to determine changelist
        ##      on the fly
        if r['Location']:
            parent_folder = self._get_parent_for_view(obj)
            # it was a successful save
            if (r['Location'] in ['../'] or
                r['Location'] == self._get_post_url(obj)):
                if parent_folder:
                    url = reverse('admin:filer-directory_listing',
                                  kwargs={'folder_id': parent_folder.id})
                else:
                    url = reverse('admin:filer-directory_listing-root')
                url = "%s%s%s%s" % (url, popup_param(request),
                                  selectfolder_param(request, "&"),
                                  current_site_param(request),)
                return HttpResponseRedirect(url)
            else:
                # this means it probably was a save_and_continue_editing
                pass
        return r


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
            if folder.is_readonly():
                return False
            # only site admins can add subfolders in site folders with no site
            if not folder.site and has_admin_role(request.user):
                return True
            # regular users need to have permissions to add folders and
            #   need to have a role over the site owner of the folder
            can_add = super(FolderPermissionModelAdmin, self).\
                has_add_permission(request)
            if (folder.site and can_add
                    and has_role_on_site(request.user, folder.site)):
                return True
        return False

    def has_change_permission(self, request, obj=None):
        folder = obj
        can_change = super(FolderPermissionModelAdmin, self).\
            has_change_permission(request, folder)

        if not folder:
            return request.user.has_perm('filer.can_use_directory_listing')

        # nobody can change core folder
        if folder.is_readonly():
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
        can_delete = super(FolderPermissionModelAdmin, self).\
            has_delete_permission(request, obj)

        if not folder:
            return can_delete

        if folder.is_readonly():
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
        if folder.is_readonly():
            return True
        # only admins can see site folders with no site owner
        if not folder.site and has_admin_role(request.user):
            return True

        if folder.site and has_role_on_site(request.user, folder.site):
            return True

        return False

class FilePermissionModelAdmin(CommonModelAdmin):

    def _get_parent_for_view(self, obj):
        return obj.folder
