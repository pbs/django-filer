#!/usr/bin/env python3
"""Test uploading images through the full ajax_upload flow to find what fails."""
import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'test_settings'
import django; django.setup()
from django.conf import settings; settings.ALLOWED_HOSTS = ['*']

from django.core.management import call_command
call_command('migrate', '--run-syncdb', verbosity=0)

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test.client import Client
from django.urls import reverse
from filer.models.filemodels import File
from filer.models.foldermodels import Folder
from filer.models.clipboardmodels import Clipboard, ClipboardItem
from PIL import Image as PILImage
import io, json

user = User.objects.filter(username='imgtest').first()
if not user:
    user = User.objects.create_superuser('imgtest', 'a@a.com', 'secret')

folder, _ = Folder.objects.get_or_create(name='img_test', owner=user)

client = Client()
client.login(username='imgtest', password='secret')

def test_upload(name, data, content_type):
    """Test uploading through ajax_upload endpoint."""
    ClipboardItem.objects.filter(clipboard__user=user).delete()
    upload = SimpleUploadedFile(name, data, content_type=content_type)
    url = reverse('admin:filer-ajax_upload', kwargs={'folder_id': folder.pk})
    response = client.post(url, {'file': upload})
    result = json.loads(response.content.decode())
    success = 'file_id' in result
    return success, result

# Test 1: Normal JPEG
print("=" * 60)
print("Test 1: Standard JPEG image")
buf = io.BytesIO()
img = PILImage.new('RGB', (800, 600), color='red')
img.save(buf, format='JPEG')
ok, res = test_upload('test1.jpg', buf.getvalue(), 'image/jpeg')
print(f"  Result: {'PASS' if ok else 'FAIL'} - {res}")

# Test 2: WebP image saved as .jpg
print("\nTest 2: WebP image saved with .jpg extension")
buf = io.BytesIO()
img = PILImage.new('RGB', (800, 600), color='blue')
img.save(buf, format='WEBP')
ok, res = test_upload('test2.jpg', buf.getvalue(), 'image/webp')
print(f"  Result: {'PASS' if ok else 'FAIL'} - {res}")

# Test 3: WebP image with .webp extension
print("\nTest 3: WebP image with proper .webp extension")
buf = io.BytesIO()
img = PILImage.new('RGB', (800, 600), color='green')
img.save(buf, format='WEBP')
ok, res = test_upload('test3.webp', buf.getvalue(), 'image/webp')
print(f"  Result: {'PASS' if ok else 'FAIL'} - {res}")

# Test 4: JPEG image with no extension
print("\nTest 4: JPEG image with no extension")
buf = io.BytesIO()
img = PILImage.new('RGB', (800, 600), color='yellow')
img.save(buf, format='JPEG')
ok, res = test_upload('image_no_ext', buf.getvalue(), 'image/jpeg')
print(f"  Result: {'PASS' if ok else 'FAIL'} - {res}")

# Test 5: Large JPEG image (high resolution)
print("\nTest 5: Large JPEG (4000x3000)")
buf = io.BytesIO()
img = PILImage.new('RGB', (4000, 3000), color='purple')
img.save(buf, format='JPEG')
ok, res = test_upload('test5_large.jpg', buf.getvalue(), 'image/jpeg')
print(f"  Result: {'PASS' if ok else 'FAIL'} - {res}")

# Test 6: JPEG with long filename
print("\nTest 6: JPEG with very long filename")
buf = io.BytesIO()
img = PILImage.new('RGB', (800, 600), color='orange')
img.save(buf, format='JPEG')
long_name = 'a' * 200 + '.jpg'
ok, res = test_upload(long_name, buf.getvalue(), 'image/jpeg')
print(f"  Result: {'PASS' if ok else 'FAIL'} - {res}")

# Test 7: JPEG with EXIF data
print("\nTest 7: JPEG with EXIF orientation data")
buf = io.BytesIO()
img = PILImage.new('RGB', (800, 600), color='cyan')
try:
    import piexif
    exif_dict = {"0th": {piexif.ImageIFD.Orientation: 6}}
    exif_bytes = piexif.dump(exif_dict)
    img.save(buf, format='JPEG', exif=exif_bytes)
except ImportError:
    print("  (piexif not available, using plain JPEG)")
    img.save(buf, format='JPEG')
ok, res = test_upload('test7_exif.jpg', buf.getvalue(), 'image/jpeg')
print(f"  Result: {'PASS' if ok else 'FAIL'} - {res}")

# Test 8: image/jpg non-standard MIME type
print("\nTest 8: Non-standard image/jpg MIME type")
buf = io.BytesIO()
img = PILImage.new('RGB', (800, 600), color='pink')
img.save(buf, format='JPEG')
ok, res = test_upload('test8.jpg', buf.getvalue(), 'image/jpg')
print(f"  Result: {'PASS' if ok else 'FAIL'} - {res}")

# Test 9: JFIF extension
print("\nTest 9: JPEG with .jfif extension")
buf = io.BytesIO()
img = PILImage.new('RGB', (800, 600), color='brown')
img.save(buf, format='JPEG')
ok, res = test_upload('test9.jfif', buf.getvalue(), 'image/jpeg')
print(f"  Result: {'PASS' if ok else 'FAIL'} - {res}")

