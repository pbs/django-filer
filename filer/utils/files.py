#-*- coding: utf-8 -*-
import os
import mimetypes

from django.utils.text import get_valid_filename as get_valid_filename_django
from django.template.defaultfilters import slugify
from django.core.files.uploadedfile import SimpleUploadedFile, InMemoryUploadedFile

from filer.settings import FILER_FILE_MODELS
from filer.utils.loader import load_object
from filer.utils.is_ajax import is_ajax


import logging
logger = logging.getLogger(__name__)

class UploadException(Exception):
    pass


def handle_upload(request):
    if not request.method == "POST":
        raise UploadException("AJAX request not valid: must be POST")
    if is_ajax(request):
        # the file is stored raw in the request
        is_raw = True
        filename = request.GET.get('qqfile', False) or request.GET.get('filename', False) or ''
        if hasattr(request, 'body'):
            # raw_post_data was depreciated in django 1.4:
            # https://docs.djangoproject.com/en/dev/releases/1.4/#httprequest-raw-post-data-renamed-to-httprequest-body
            data = request.body
        elif hasattr(request, 'raw_post_data'):
            # fallback for django 1.3
            data = request.raw_post_data
        else:
            raise UploadException("Request is not valid: there is no request body.")
        mime_type = mimetypes.guess_type(filename)[0] or "text/plain"
        upload = SimpleUploadedFile(name=filename, content=data, content_type=mime_type)
    else:
        if len(request.FILES) == 1:
            # FILES is a dictionary in Django but Ajax Upload gives the uploaded file an
            # ID based on a random number, so it cannot be guessed here in the code.
            # Rather than editing Ajax Upload to pass the ID in the querystring, note that
            # each upload is a separate request so FILES should only have one entry.
            # Thus, we can just grab the first (and only) value in the dict.
            is_raw = False
            upload = list(request.FILES.values())[0]
            filename = upload.name
        else:
            raise UploadException("AJAX request not valid: Bad Upload")
    return upload, filename, is_raw


def get_valid_filename(s):
    """
    like the regular get_valid_filename, but also slugifies away
    umlauts and stuff.
    """
    if not s:
        return ''
    s = get_valid_filename_django(s)
    filename, ext = os.path.splitext(s)
    filename = slugify(filename)
    ext = slugify(ext)
    if ext:
        return "%s.%s" % (filename, ext)
    else:
        return "%s" % (filename,)


def matching_file_subtypes(filename, file_pointer, request):
    """
    Returns a list of valid subtypes for a given file.
    """
    types = list(map(load_object, FILER_FILE_MODELS))

    def _match_subtype(subtype):
        is_match = subtype.matches_file_type(filename, file_pointer, request)
        return is_match
    type_matches = list(filter(_match_subtype, types))
    return type_matches


def truncate_filename(upload, maxlen=None):
    """
    Return truncated filename
    Pre-extension filename will be less than or equals maxlen(if passed)
    """
    title, extension = os.path.splitext(upload.name)
    filename = '{title}.{ext}'.format(title=title[:maxlen], ext=extension.lstrip('.'))
    return filename

def save_first_n_bytes_to_file(in_memory_file, destination_path , num_bytes):
    """
    Reads the first 'num_bytes' from an InMemoryUploadedFile and saves them to a new file on disk.

    Args:
        in_memory_file: The InMemoryUploadedFile object received (e.g., from request.FILES).
        destination_path: The full path (including filename) where the bytes should be saved.
                          Example: "my_output_dir/first_100_bytes.bin"
        num_bytes: The number of bytes to read and save from the beginning of the file.
                   Defaults to 100.
    """
    if not isinstance(in_memory_file, InMemoryUploadedFile):
        logger.error(f"Error: Expected an InMemoryUploadedFile, but got {type(in_memory_file)}")
        return

    try:
        # Ensure the file pointer is at the beginning before reading
        # This is crucial because a file-like object's pointer might have moved
        # if it was already accessed elsewhere (e.g., for type detection).
        in_memory_file.seek(0)

        # Read the specified number of bytes
        first_bytes = in_memory_file.read(num_bytes)

        # Ensure the destination directory exists
        output_dir = os.path.dirname(destination_path)
        if output_dir: # Only create if path includes a directory
            os.makedirs(output_dir, exist_ok=True)

        # Write the bytes to the new file on disk in binary mode
        with open(destination_path, 'wb') as f_out:
            f_out.write(first_bytes)

    except Exception as e:
        logger.error(f"An error occurred while saving the bytes: {e}")
