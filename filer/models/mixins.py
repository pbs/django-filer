import warnings

from django.db import models
from django.templatetags.static import static
from django.utils.translation import gettext_lazy as _

from ..settings import FILER_ADMIN_ICON_SIZES


class IconsMixin:
    """
    Can be used on any model that has a _icon attribute. will return a dict
    containing urls for icons of different sizes with that name.
    """
    @property
    def icons(self):
        r = {}
        if getattr(self, '_icon', False):
            for size in FILER_ADMIN_ICON_SIZES:
                try:
                    r[size] = static("filer/icons/{}_{}x{}.png".format(
                        self._icon, size, size))
                except ValueError:
                    pass
        return r


# PBS-specific: trashable decorator
def trashable(cls):

    deleted_at = models.DateTimeField(
        _('deleted at'), editable=False, blank=True, null=True)

    for custom_method in ['soft_delete', 'hard_delete', 'restore']:
        if not hasattr(cls, custom_method):
            raise NotImplementedError("Method %s required." % custom_method)

    def is_in_trash(instance):
        return instance.deleted_at is not None

    # custom delete method
    def delete_restorable(instance, *args, **kwargs):
        to_trash = kwargs.pop('to_trash', True)
        if not instance.deleted_at and to_trash:
            instance.soft_delete(*args, **kwargs)
        else:
            instance.hard_delete(*args, **kwargs)

    # override delete method
    def delete(instance, *args, **kwargs):
        delete_restorable(instance, *args, **kwargs)
    delete.alters_data = True

    cls.add_to_class('is_in_trash', is_in_trash)
    cls.add_to_class('delete_restorable', delete_restorable)
    cls.add_to_class('delete', delete)
    cls.add_to_class('deleted_at', deleted_at)
    return cls
