import mimetypes

from django import forms
from django.contrib.admin.templatetags.admin_urls import admin_urlname
from django.contrib.admin.utils import unquote
from django.contrib.staticfiles.storage import staticfiles_storage
from django.db import models
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from django.utils.safestring import mark_safe
from django.utils.timezone import now
from django.utils.translation import gettext as _

from easy_thumbnails.engine import NoSourceGenerator
from easy_thumbnails.exceptions import InvalidImageFormatError
from easy_thumbnails.files import get_thumbnailer
from easy_thumbnails.models import Thumbnail as EasyThumbnail
from easy_thumbnails.options import ThumbnailOptions

from .. import settings
from ..models import File
from ..settings import DEFERRED_THUMBNAIL_SIZES
from ..utils.loader import load_model
from .permissions import PrimitivePermissionAwareModelAdmin
from .tools import AdminContext, admin_url_params_encoded, popup_status

# PBS-specific imports
from .common_admin import FilePermissionModelAdmin
from ..fields.file import NonClearableFileInput

try:
    from ..models import BaseImage
except ImportError:
    BaseImage = None

Image = load_model(settings.FILER_IMAGE_MODEL)


class FileAdminChangeFrom(forms.ModelForm):
    class Meta:
        model = File
        exclude = ()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "file" in self.fields:
            self.fields["file"].widget = forms.FileInput()

    def clean(self):
        from ..validation import validate_upload
        cleaned_data = super().clean()
        if "file" in self.changed_data and cleaned_data["file"]:
            mime_type = mimetypes.guess_type(cleaned_data["file"].name)[0] or 'application/octet-stream'
            file = cleaned_data["file"]
            file.open("w+")  # Allow for sanitizing upload
            file.seek(0)
            validate_upload(
                file_name=cleaned_data["file"].name,
                file=file.file,
                owner=cleaned_data.get("owner"),
                mime_type=mime_type,
            )
            file.open("r")
        return self.cleaned_data


class FileAdmin(PrimitivePermissionAwareModelAdmin):
    list_display = ('label',)
    list_per_page = 10
    search_fields = ['name', 'original_filename', 'sha1', 'description']
    readonly_fields = ('sha1', 'display_canonical')

    form = FileAdminChangeFrom

    formfield_overrides = {
        models.FileField: {'widget': NonClearableFileInput},
    }

    # PBS-specific: make fields readonly for restricted/core files
    def get_readonly_fields(self, request, obj=None):
        if obj and (obj.is_readonly_for_user(request.user) or
                    obj.is_restricted_for_user(request.user)):
            return [field.name for field in obj.__class__._meta.fields]
        readonly = list(self.readonly_fields)
        self._make_restricted_field_readonly(request.user, obj)
        if not request.user.is_superuser:
            if 'owner' not in readonly:
                readonly.append('owner')
        return readonly

    def _make_restricted_field_readonly(self, user, obj):
        """PBS: make restricted field readonly if user can't change restriction."""
        if obj and hasattr(obj, 'can_change_restricted'):
            if not obj.can_change_restricted(user):
                if 'restricted' not in self.readonly_fields:
                    self.readonly_fields = list(self.readonly_fields) + ['restricted']

    @classmethod
    def build_fieldsets(cls, extra_main_fields=(), extra_advanced_fields=(),
                        extra_fieldsets=()):
        fieldsets = (
            (None, {
                'fields': (
                    'title',
                    'owner',
                    'description',
                ) + extra_main_fields,
            }),
            (_('Advanced'), {
                'fields': (
                    'file',
                    'name',
                    'sha1',
                    'display_canonical',
                ) + extra_advanced_fields,
                'classes': ('collapse',),
            }),
            (_('Permissions'), {
                'fields': ('restricted',),
                'classes': ('collapse', 'wide', 'extrapretty'),
            }),
        ) + extra_fieldsets
        if settings.FILER_ENABLE_PERMISSIONS:
            fieldsets = fieldsets + (
                (None, {
                    'fields': ('is_public',)
                }),
            )
        return fieldsets

    def response_change(self, request, obj):
        if (
            request.POST
            and '_continue' not in request.POST
            and '_saveasnew' not in request.POST
            and '_addanother' not in request.POST
            and '_edit_from_widget' not in request.POST
        ):
            if obj.folder:
                url = reverse('admin:filer-directory_listing',
                              kwargs={'folder_id': obj.folder.id})
            else:
                url = reverse(
                    'admin:filer-directory_listing-unfiled_images')
            url = "{}{}".format(
                url,
                admin_url_params_encoded(request),
            )
            return HttpResponseRedirect(url)

        template_response = super().response_change(request, obj)
        if hasattr(template_response, 'context_data'):
            template_response.context_data["media"] = self.media
        return template_response

    def render_change_form(self, request, context, add=False, change=False,
                           form_url='', obj=None):
        context.update({
            'show_delete': True,
            'history_url': admin_urlname(self.opts, 'history'),
            'expand_image_url': None,
            'is_popup': popup_status(request),
            'filer_admin_context': AdminContext(request),
        })
        if obj and obj.mime_maintype == 'image' and obj.file.exists():
            if 'svg' in obj.mime_type:
                context['expand_image_url'] = reverse(admin_urlname(Image._meta, 'expand'), args=(obj.pk,))
            else:
                context['expand_image_url'] = obj.file.url
        return super().render_change_form(
            request=request, context=context, add=add, change=change,
            form_url=form_url, obj=obj)

    def delete_view(self, request, object_id, extra_context=None):
        try:
            obj = self.get_queryset(request).get(pk=unquote(object_id))
            parent_folder = obj.folder
        except self.model.DoesNotExist:
            parent_folder = None

        if request.POST:
            super().delete_view(
                request=request, object_id=object_id,
                extra_context=extra_context)
            if parent_folder:
                url = reverse('admin:filer-directory_listing',
                              kwargs={'folder_id': parent_folder.id})
            else:
                url = reverse('admin:filer-directory_listing-unfiled_images')
            url = "{}{}".format(
                url,
                admin_url_params_encoded(request)
            )
            return HttpResponseRedirect(url)

        return super().delete_view(
            request=request, object_id=object_id,
            extra_context=extra_context)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        if not obj:
            return False
        return super().has_change_permission(request, obj)

    def has_view_permission(self, request, obj=None):
        if not obj:
            return False
        return super().has_view_permission(request, obj)

    def get_model_perms(self, request):
        return {
            'add': False,
            'change': False,
            'delete': False,
        }

    def display_canonical(self, instance):
        canonical = instance.canonical_url
        if canonical:
            return mark_safe(f'<a href="{canonical}">{canonical}</a>')
        else:
            return '-'
    display_canonical.allow_tags = True
    display_canonical.short_description = _('canonical URL')

    def get_urls(self):
        return super().get_urls() + [
            path("icon/<int:file_id>/<int:size>",
                 self.admin_site.admin_view(self.icon_view),
                 name=f"filer_{self.model._meta.model_name}_fileicon")
        ]

    def icon_view(self, request, file_id: int, size: int) -> HttpResponse:
        if size not in DEFERRED_THUMBNAIL_SIZES:
            raise Http404
        file = get_object_or_404(File, pk=file_id)
        if BaseImage and not isinstance(file, BaseImage):
            raise Http404()

        try:
            thumbnailer = get_thumbnailer(file)
            thumbnail_options = ThumbnailOptions({'size': (size, size), "crop": True})
            thumbnail = thumbnailer.get_thumbnail(thumbnail_options, generate=True)
            EasyThumbnail.objects.filter(name=thumbnail.name).update(modified=now())
            return HttpResponseRedirect(thumbnail.url)
        except (InvalidImageFormatError, NoSourceGenerator):
            return HttpResponseRedirect(staticfiles_storage.url('filer/icons/file-missing.svg'))


FileAdmin.fieldsets = FileAdmin.build_fieldsets()
