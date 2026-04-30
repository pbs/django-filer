from django.conf import settings
from django.contrib.auth import models as auth_models
from django.db import models
from django.utils.translation import gettext_lazy as _

from . import filemodels


class Clipboard(models.Model):
    user = models.OneToOneField(
        getattr(settings, 'AUTH_USER_MODEL', 'auth.User'),
        verbose_name=_('user'),
        related_name="filer_clipboard",
        on_delete=models.CASCADE,
    )

    files = models.ManyToManyField(
        'File',
        verbose_name=_('files'),
        related_name="in_clipboards",
        through='ClipboardItem',
    )

    # PBS-specific: folder_name used for clipboard upload paths
    folder_name = "_clipboard"

    class Meta:
        app_label = 'filer'
        verbose_name = _("clipboard")
        verbose_name_plural = _("clipboards")

    def append_file(self, file_obj):
        try:
            self.files.get(pk=file_obj.pk)
            return False
        except filemodels.File.DoesNotExist:
            newitem = ClipboardItem(file=file_obj, clipboard=self)
            newitem.save()
            return True

    def empty(self):
        for item in self.bucket_items.all():
            item.delete()
    empty.alters_data = True

    def __str__(self):
        return f"Clipboard {self.id} of {self.user}"


class ClipboardItem(models.Model):
    file = models.ForeignKey(
        'File',
        verbose_name=_("file"),
        on_delete=models.CASCADE,
    )

    clipboard = models.ForeignKey(
        Clipboard,
        verbose_name=_("clipboard"),
        on_delete=models.CASCADE,
    )

    class Meta:
        app_label = 'filer'
        verbose_name = _("clipboard item")
        verbose_name_plural = _("clipboard items")
