import logging
from datetime import datetime

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.timezone import get_current_timezone, make_aware, now
from django.utils.translation import gettext_lazy as _

from .abstract import BaseImage


logger = logging.getLogger("filer")


# This is the standard Image model which can be swapped for a custom model using FILER_IMAGE_MODEL setting
class Image(BaseImage):
    date_taken = models.DateTimeField(
        _("date taken"),
        null=True,
        blank=True,
        editable=False,
    )

    author = models.CharField(
        _("author"),
        max_length=255,
        null=True,
        blank=True,
    )

    default_credit = models.CharField(
        _('default credit text'), max_length=255, blank=True, null=True,
        help_text=_('Credit text gives credit to the owner or licensor of '
                    'an image; it is displayed below the image plugin, or '
                    'below the caption text on an image plugin, if that '
                    'option is selected; it is displayed along the bottom '
                    'of an image in the photo gallery plugin; there is a '
                    '30-character limit, including spaces.'))

    must_always_publish_author_credit = models.BooleanField(
        _("must always publish author credit"),
        default=False,
    )

    must_always_publish_copyright = models.BooleanField(
        _('must always publish copyright'),
        default=False,
    )

    class Meta(BaseImage.Meta):
        swappable = 'FILER_IMAGE_MODEL'
        default_manager_name = 'objects'

    def clean(self):
        if self.default_credit:
            self.default_credit = self.default_credit.strip()
        if self.default_alt_text:
            self.default_alt_text = self.default_alt_text.strip()
        if self.default_caption:
            self.default_caption = self.default_caption.strip()

        if int(len(self.default_credit or '')) > 30:
            raise ValidationError(
                "Ensure default credit text has at most 30 characters ("
                "%s characters found)." % len(self.default_credit))
        super().clean()

    def save(self, *args, **kwargs):
        if self.date_taken is None:
            try:
                exif_date = self.exif.get('DateTimeOriginal', None)
                if exif_date is not None:
                    d, t = exif_date.split(" ")
                    year, month, day = d.split(':')
                    hour, minute, second = t.split(':')
                    if getattr(settings, "USE_TZ", False):
                        tz = get_current_timezone()
                        self.date_taken = make_aware(datetime(
                            int(year), int(month), int(day),
                            int(hour), int(minute), int(second)), tz)
                    else:
                        self.date_taken = datetime(
                            int(year), int(month), int(day),
                            int(hour), int(minute), int(second))
            except Exception:
                pass
        if self.date_taken is None:
            self.date_taken = now()
        super().save(*args, **kwargs)
