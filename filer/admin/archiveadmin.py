from filer.admin.fileadmin import FileAdmin, FileAdminChangeFrom
from filer.models import Archive


class ArchiveAdminForm(FileAdminChangeFrom):

    class Meta:
        model = Archive
        exclude = ()


class ArchiveAdmin(FileAdmin):
    form = ArchiveAdminForm
