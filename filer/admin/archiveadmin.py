from django import forms
from django.contrib import admin
from filer.admin.fileadmin import FileAdmin
from filer.models import Archive


class ArchiveAdminForm(forms.ModelForm):

    class Meta:
        model = Archive
        exclude = ()


class ArchiveAdmin(FileAdmin):
    form = ArchiveAdminForm
