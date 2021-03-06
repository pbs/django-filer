#-*- coding: utf-8 -*-
from django.db import models
from django.utils.translation import ugettext  as _
from filer.admin.common_admin import FilePermissionModelAdmin
from filer.fields.file import NonClearableFileInput


class FileAdmin(FilePermissionModelAdmin):
    list_display = ('label',)
    list_per_page = 10
    search_fields = ['name', 'original_filename', 'sha1', 'description']
    raw_id_fields = ('owner',)
    readonly_fields = ('sha1', )

    formfield_overrides = {
        models.FileField:       {'widget': NonClearableFileInput},
    }

    def get_readonly_fields(self, request, obj=None):
        if obj and (obj.is_readonly_for_user(request.user) or
                    obj.is_restricted_for_user(request.user)):
            return [field.name
                    for field in obj.__class__._meta.fields]
        self.readonly_fields = [ro_field
                                for ro_field in self.readonly_fields]
        self._make_restricted_field_readonly(request.user, obj)
        if not request.user.is_superuser:
            # allow owner to be editable only by superusers
            self.readonly_fields += ['owner']
        return super(FileAdmin, self).get_readonly_fields(
            request, obj)

    @classmethod
    def build_fieldsets(cls, extra_main_fields=(), extra_advanced_fields=(), extra_fieldsets=()):
        fieldsets = (
            (None, {
                'fields': ('title', 'owner', 'description',) + extra_main_fields,
            }),
            (_('Advanced'), {
                # due to custom requirements: sha1 field should be hidden
                # 'fields': ('file', 'sha1',) + extra_advanced_fields,
                'fields': ('file', 'name',) + extra_advanced_fields,
                'classes': ('collapse',),
                }),
            (('Permissions'), {
                'fields': ('restricted',),
                'classes': ('collapse', 'wide', 'extrapretty'),
                })
            ) + extra_fieldsets
        return fieldsets

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        if not obj:
            # We do this in order to prevent access to the change_list view
            return False
        return super(FileAdmin, self).has_change_permission(request, obj)

    def get_model_perms(self, request):
        """
        While this method is used by Django, it is no longer used to determine if the
        option is available in the changelist view, which was the original intention.
        The has_xxx_permission is used instead.
        """
        return {
            'add': self.has_add_permission(request),
            'change': self.has_change_permission(request),
            'delete': False,
        }

FileAdmin.fieldsets = FileAdmin.build_fieldsets()
