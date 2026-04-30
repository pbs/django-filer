from django.contrib import admin

from ..models import Clipboard, File, Folder, FolderPermission
from ..settings import FILER_IMAGE_MODEL
from ..utils.loader import load_model
from .clipboardadmin import ClipboardAdmin
from .fileadmin import FileAdmin
from .folderadmin import FolderAdmin
from .imageadmin import ImageAdmin
from .permissionadmin import PermissionAdmin

# PBS-specific: ThumbnailOption model may not exist in PBS migrations yet
try:
    from ..models import ThumbnailOption
    from .thumbnailoptionadmin import ThumbnailOptionAdmin
    _has_thumbnail_option = True
except ImportError:
    _has_thumbnail_option = False

# PBS-specific: Trash admin
from ..admin.trashadmin import Trash, TrashAdmin

Image = load_model(FILER_IMAGE_MODEL)

admin.site.register(Folder, FolderAdmin)
admin.site.register(File, FileAdmin)
admin.site.register(Clipboard, ClipboardAdmin)
admin.site.register(Image, ImageAdmin)
admin.site.register(FolderPermission, PermissionAdmin)

if _has_thumbnail_option:
    admin.site.register(ThumbnailOption, ThumbnailOptionAdmin)

# PBS-specific: register Trash admin
admin.site.register([Trash], TrashAdmin)

# PBS-specific: Archive (backward compat)
try:
    from ..models import Archive
    from ..admin.archiveadmin import ArchiveAdmin
    admin.site.register(Archive, ArchiveAdmin)
except ImportError:
    pass
