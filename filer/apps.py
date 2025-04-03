from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _
from filer import __version__ as filer_version


class FilerConfig(AppConfig):
    name = 'filer'
    verbose_name = _(f"Filer ({filer_version})")