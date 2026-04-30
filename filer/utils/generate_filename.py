import os
import uuid

from django.core.exceptions import ObjectDoesNotExist
from django.core.files.uploadedfile import UploadedFile
from django.utils.encoding import force_str
from django.utils.timezone import now

import filer

from .files import get_valid_filename


def by_date(instance, filename):
    datepart = force_str(now().strftime("%Y/%m/%d"))
    return os.path.join(datepart, get_valid_filename(filename))


def randomized(instance, filename):
    uuid_str = str(uuid.uuid4())
    return os.path.join(uuid_str[0:2], uuid_str[2:4], uuid_str,
                        get_valid_filename(filename))


class prefixed_factory:
    def __init__(self, upload_to, prefix):
        self.upload_to = upload_to
        self.prefix = prefix

    def __call__(self, instance, filename):
        if callable(self.upload_to):
            upload_to_str = self.upload_to(instance, filename)
        else:
            upload_to_str = self.upload_to
        if not self.prefix:
            return upload_to_str
        return os.path.join(self.prefix, upload_to_str)


# PBS-specific: path-based filename generation

def _is_in_memory(file_):
    return isinstance(file_, UploadedFile)


def _construct_logical_folder_path(filer_file):
    return os.path.join(*(folder.name for folder in filer_file.logical_path))


def _goes_to_clipboard(instance):
    return instance.folder is None or (
        instance.pk is None and _is_in_memory(instance.file.file))


def by_path(instance, filename):
    if _goes_to_clipboard(instance):
        from filer.models import Clipboard
        try:
            owner_name = instance.owner.username if instance.owner else '_missing_owner'
        except (AttributeError, ObjectDoesNotExist):
            owner_name = '_missing_owner'
        return os.path.join(
            Clipboard.folder_name,
            owner_name,
            filename)
    else:
        return os.path.join(
            _construct_logical_folder_path(instance),
            instance.actual_name)


def get_trash_path(instance):
    path = [filer.settings.FILER_TRASH_PREFIX]
    path.append("%s" % instance.pk)
    path.append(instance.pretty_logical_path.strip('/'))
    return os.path.join(*path)
