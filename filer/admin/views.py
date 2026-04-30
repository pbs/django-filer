from django import forms
from django.contrib import admin
from django.contrib.admin import widgets
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.http.response import HttpResponseBadRequest
from django.template.response import TemplateResponse
from django.utils.translation import gettext_lazy as _

from .. import settings as filer_settings
from ..models import Clipboard, Folder, FolderRoot, tools
from .tools import AdminContext, admin_url_params_encoded, popup_status


class NewFolderForm(forms.ModelForm):
    class Meta:
        model = Folder
        fields = ('name', 'site')
        widgets = {
            'name': widgets.AdminTextInputWidget,
        }

    def __init__(self, *args, **kwargs):
        self.is_root_folder = kwargs.pop('is_root_folder', True)
        super().__init__(*args, **kwargs)
        if self.is_root_folder:
            self.fields['site'].required = True
        else:
            # Hide site field for child folders
            if 'site' in self.fields:
                del self.fields['site']

    def clean(self):
        cleaned_data = super().clean()
        if self.is_root_folder and not cleaned_data.get('site'):
            raise forms.ValidationError('Site is required')
        return cleaned_data


@login_required
def make_folder(request, folder_id=None):
    if not folder_id:
        folder_id = request.GET.get('parent_id')
    if not folder_id:
        folder_id = request.POST.get('parent_id')
    if folder_id:
        try:
            folder = Folder.objects.get(id=folder_id)
        except Folder.DoesNotExist:
            raise PermissionDenied
    else:
        folder = None

    if folder and not folder.has_add_permission(request.user):
        raise PermissionDenied
    elif request.user.is_superuser:
        pass
    elif folder is None:
        # regular users may not add root folders unless configured otherwise
        if not filer_settings.FILER_ALLOW_REGULAR_USERS_TO_ADD_ROOT_FOLDERS:
            raise PermissionDenied
    elif not folder.has_add_children_permission(request):
        # the user does not have the permission to add subfolders
        raise PermissionDenied

    if request.method == 'POST':
        new_folder_form = NewFolderForm(request.POST, is_root_folder=(folder is None))
        if new_folder_form.is_valid():
            new_folder = new_folder_form.save(commit=False)
            if (folder or FolderRoot()).contains_folder(new_folder.name):
                new_folder_form._errors['name'] = new_folder_form.error_class(
                    [_('Folder with this name already exists.')])
            else:
                new_folder.parent = folder
                new_folder.owner = request.user
                new_folder.save()
                if popup_status(request):
                    context = admin.site.each_context(request)
                    return TemplateResponse(request, 'admin/filer/dismiss_popup.html', context)
                else:
                    from django.urls import reverse
                    if folder:
                        url = reverse('admin:filer-directory_listing', kwargs={'folder_id': folder.id})
                    else:
                        url = reverse('admin:filer-directory_listing-root')
                    return HttpResponseRedirect(url)
    else:
        new_folder_form = NewFolderForm(is_root_folder=(folder is None))

    context = admin.site.each_context(request)
    context.update({
        'opts': Folder._meta,
        'new_folder_form': new_folder_form,
        'is_popup': popup_status(request),
        'filer_admin_context': AdminContext(request),
    })
    return TemplateResponse(request, 'admin/filer/folder/new_folder_form.html', context)


@login_required
def paste_clipboard_to_folder(request):

    if request.method == 'POST':
        folder = Folder.objects.get(id=request.POST.get('folder_id'))
        clipboard = Clipboard.objects.get(id=request.POST.get('clipboard_id'))
        if folder.has_add_children_permission(request):
            tools.move_files_from_clipboard_to_folder(request, clipboard, folder)
            tools.discard_clipboard(clipboard)
        else:
            raise PermissionDenied
    redirect = request.GET.get('redirect_to', '')
    if not redirect:
        redirect = request.POST.get('redirect_to', '')
    return HttpResponseRedirect(
        '{}?order_by=-modified_at{}'.format(
            redirect,
            admin_url_params_encoded(request, first_separator='&'),
        )
    )


@login_required
def discard_clipboard(request):
    if request.method == 'POST':
        clipboard = Clipboard.objects.get(id=request.POST.get('clipboard_id'))
        tools.discard_clipboard(clipboard)
    return HttpResponseRedirect(
        '{}{}'.format(
            request.POST.get('redirect_to', ''),
            admin_url_params_encoded(request, first_separator='&'),
        )
    )


@login_required
def delete_clipboard(request):

    if request.method == 'POST':
        clipboard = Clipboard.objects.get(id=request.POST.get('clipboard_id'))
        tools.delete_clipboard(clipboard)
    return HttpResponseRedirect(
        '{}{}'.format(
            request.POST.get('redirect_to', ''),
            admin_url_params_encoded(request, first_separator='&'),
        )
    )
