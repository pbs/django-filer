#-*- coding: utf-8 -*-
from django.contrib import admin
from django.contrib.admin.utils import unquote
from django.contrib.admin.options import IS_POPUP_VAR
from django.contrib.auth import get_permission_codename
from django.core.urlresolvers import reverse, resolve
from django.http import HttpResponseRedirect

from filer.models import Folder, File
from filer.admin.tools import (has_admin_role, has_role_on_site,
                               can_restrict_on_site,
                               has_multi_file_action_permission)
from filer.views import (popup_param, selectfolder_param, popup_status,
                         selectfolder_status, current_site_param,
                         get_param_from_request)


class CommonModelAdmin(admin.ModelAdmin):
    save_as = False

    def _make_restricted_field_readonly(self, user, obj=None):
        perm = 'filer.can_restrict_operations'
        can_restrict = user.has_perm(perm, obj) or user.has_perm(perm)
        if not can_restrict or (obj and not obj.can_change_restricted(user)):
            if 'restricted' not in self.readonly_fields:
                self.readonly_fields += ['restricted']
        else:
            if 'restricted' in self.readonly_fields:
                self.readonly_fields.remove('restricted')

    def _get_post_url(self, obj):
        """
        Needed to retrieve the changelist url as Folder/File can be extended
            and admin url may change
        """
        # Code borrowed from django ModelAdmin to determine
        #      changelist on the fly
        opts = obj._meta
        module_name = opts.model_name
        return reverse('admin:%s_%s_changelist' %
                       (opts.app_label, module_name),
            current_app=self.admin_site.name)

    def _get_parent_for_view(self, obj):
        return obj.parent

    def _redirect_to_directory_listing(
            self, request, response, expected_urls, parent, current_obj):
        """
        Overrides the default to enable redirecting to the directory view after
        change/delete of a file/folder.
        """
        url = response.get("Location", None)
        if url in expected_urls or url == self._get_post_url(current_obj):
            return self._make_redirect_to_parent(request, parent)
        return response

    def _make_redirect_to_parent(self, request, parent):
        if parent:
            url = reverse('admin:filer-directory_listing', kwargs={'folder_id': parent.id})
        else:
            url = reverse('admin:filer-directory_listing-root')

        url = "%s%s%s%s" % (url, popup_param(request),
                            selectfolder_param(request, "&"),
                            current_site_param(request),)
        return HttpResponseRedirect(url)


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
            obj = self.get_queryset(request).get(pk=unquote(object_id))
            parent_folder = self._get_parent_for_view(obj)
        except self.model.DoesNotExist:
            obj = None
        expected_urls = ["../../../../", "../../"]

        response = super(CommonModelAdmin, self).delete_view(
            request=request, object_id=object_id,
            extra_context=extra_context)

        return self._redirect_to_directory_listing(
            request, response, expected_urls, parent_folder, obj)

    def has_change_permission(self, request, obj=None):
        """
        Implemented to allow auth backends to handle object permissions.
        """
        opts = self.opts
        if opts.auto_created:
            # The model was auto-created as intermediary for a
            # ManyToMany-relationship, find the target model
            for field in opts.fields:
                if field.rel and field.rel.to != self.parent_model:
                    opts = field.rel.to._meta
                    break
        codename = get_permission_codename('change', opts)
        perm_name, user = "{}.{}".format(opts.app_label, codename), request.user
        return user.has_perm(perm_name, obj) or user.has_perm(perm_name)

    def has_delete_permission(self, request, obj=None):
        """
        Implemented to allow auth backends to handle object permissions.
        """
        if self.opts.auto_created:
            # For link objects
            return self.has_change_permission(request, obj)
        codename = get_permission_codename('delete', self.opts)
        perm_name, user = "{}.{}".format(self.opts.app_label, codename), request.user
        return user.has_perm(perm_name, obj) or user.has_perm(perm_name)

    def render_change_form(self, request, context, add=False, change=False,
                           form_url='', obj=None):
        context.update({
            'current_site': get_param_from_request(request, 'current_site'),
            'show_delete': True,
            'is_popup': popup_status(request),
            'select_folder': selectfolder_status(request),
        })
        return super(CommonModelAdmin, self).render_change_form(
            request=request, context=context, add=False,
            change=change, form_url=form_url, obj=obj)

    def response_change(self, request, obj):
        """
        Overrides the default to be able to forward to the directory listing
        instead of the default change_list_view
        """
        parent_folder = self._get_parent_for_view(obj)
        if IS_POPUP_VAR in request.POST:
            # In popup we always want to see the parent after changes
            return self._make_redirect_to_parent(request, parent_folder)
        response = super(CommonModelAdmin, self).response_change(request, obj)
        expected_urls = ['../', reverse('admin:index')]
        return self._redirect_to_directory_listing(
            request, response, expected_urls, parent_folder, obj)


class FolderPermissionModelAdmin(CommonModelAdmin):

    def has_add_permission(self, request):
        # allow only make folder view
        current_view = resolve(request.path_info).url_name
        if not current_view == 'filer-directory_listing-make_root_folder':
            return False

        folder_id = get_param_from_request(request, 'parent_id')
        if not folder_id:
            # only site admins and superusers can add root folders
            if has_admin_role(request.user):
                return True
        else:
            folder = Folder.objects.get(id=folder_id)
            return folder.has_add_permission(request.user)
        return False

    def has_change_permission(self, request, obj=None):
        folder = obj
        can_change = super(FolderPermissionModelAdmin, self).\
            has_change_permission(request, folder)

        if not folder:
            return request.user.has_perm('filer.can_use_directory_listing')

        return folder.has_change_permission(request.user)

    def has_delete_permission(self, request, obj=None):
        folder = obj
        can_delete = super(FolderPermissionModelAdmin, self).\
            has_delete_permission(request, obj)

        if not can_delete or not folder:
            return can_delete

        if request.method == 'POST':
            return has_multi_file_action_permission(
                request, File.objects.none(),
                Folder.objects.filter(id=folder.id))

        return folder.has_delete_permission(request.user)

    def can_view_folder_content(self, request, folder):
        if folder.is_readonly_for_user(request.user):
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

    def has_change_permission(self, request, obj=None):
        can_change = super(FilePermissionModelAdmin, self).\
            has_change_permission(request, obj)
        if not can_change or not obj:
            return can_change
        return obj.has_change_permission(request.user)

    def has_delete_permission(self, request, obj=None):
        can_delete = super(FilePermissionModelAdmin, self).\
            has_delete_permission(request, obj)
        if not can_delete or not obj:
            return can_delete
        return obj.has_delete_permission(request.user)
