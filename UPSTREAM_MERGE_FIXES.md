# Upstream Merge Fix Progress

## Overview

**Upstream source:** `https://github.com/django-cms/django-filer` (master branch, v3.4.4)  
**Fork divergence:** Forked at tag `0.9` (commit `a9364960`), ~790 PBS vs ~1,977 upstream commits, 603 files changed.  
**Target:** Django 5.1 / Python 3.12+

### Test Results Timeline

| Stage | Failed | Passed | Skipped |
|-------|--------|--------|---------|
| Pre-merge (PBS baseline) | 0 | 153 | 68 |
| After upstream merge | 73 | ~80 | 68 |
| After Session 1 fixes | 67 | 86 | 68 |
| After Session 2 fixes | 59 | 94 | 68 |
| **After all fixes (final)** | **0** | **153** | **68** |

---

## Fixes Applied

### 1. `setup.py` — Build-time import error (GHA blocker)

- **Problem:** `__import__('filer').__version__` fails because Django isn't installed in the build environment
- **Fix:** Replaced with regex-based `get_version()` that reads `filer/__init__.py` without importing
- **Also:** Removed deprecated `setuptools.command.test` references and `test_suite`/`tests_require`
- **Code:**
  ```python
  def get_version():
      """Read version from filer/__init__.py without importing the package."""
      init_py = os.path.join(os.path.dirname(__file__), 'filer', '__init__.py')
      with open(init_py) as f:
          match = re.search(r"^__version__\s*=\s*['\"]([^'\"]+)['\"]", f.read(), re.M)
      if not match:
          raise RuntimeError("Cannot find __version__ in filer/__init__.py")
      return match.group(1)
  ```

### 2. `filer/__init__.py` — PEP 440 version

- **Problem:** `3.5.0.pbs.1` is invalid per PEP 440
- **Fix:** Changed to `3.5.0+pbs.1` (local version identifier)

### 3. `filer/models/abstract.py` — VILImage import

- **Problem:** `from easy_thumbnails.VIL import Image` fails without `reportlab`
- **Fix:** Wrapped in try/except, set `VILImage = None` as fallback
- **Code:**
  ```python
  try:
      from easy_thumbnails.VIL import Image as VILImage
  except (ImportError, ModuleNotFoundError):
      VILImage = None
  ```

### 4. `filer/admin/fileadmin.py` — `display_canonical` FieldError

- **Problem:** `get_readonly_fields` returned only model field names for restricted/core files, but fieldsets contain `display_canonical` (an admin method, not a model field)
- **Fix:** Appended `'display_canonical'` to the readonly fields list in that code path
- **Error:** `FieldError: Unknown field(s) (display_canonical) specified for File`

### 5. `filer/templates/admin/filer/submit_line.html` — Delete URL with empty pk

- **Problem:** `{% url opts|admin_urlname:'delete' obj.pk %}` failed when `obj.pk` was empty
- **Fix:** Changed to `original.pk` and added `and original.pk` guard

### 6. `filer/admin/folderadmin.py` — Multiple fixes

#### 6a. `destination_folders` AJAX view
- **Problem:** `NoReverseMatch: 'filer-destination_folders' not found` — the fancytree folder picker widget needed this URL
- **Fix:** Added AJAX view and URL pattern to `FolderAdmin.get_urls()`

#### 6b. `move_file_to_clipboard` signature mismatch
- **Problem:** Both call sites passed wrong number of arguments
- **Fix:** Added missing `request` argument at both call sites

#### 6c. `KeyError: 'name'` in folder form clean
- **Problem:** Folder form clean method assumed `'name'` was always in `cleaned_data`
- **Fix:** Added guard `if 'name' not in cleaned_data: return cleaned_data`

#### 6d. `exclude` tuple incomplete
- **Problem:** Upstream had `exclude = ('parent',)` but PBS needs `('parent', 'owner', 'folder_type')`
- **Fix:** Restored full PBS exclude tuple

#### 6e. `get_form()` — PBS field visibility logic
- **Problem:** Upstream `get_form()` didn't handle PBS-specific dynamic field visibility
- **Fix:** Restored full PBS logic:
  - Hide `site`/`shared` for child folders and core folders
  - Only show `shared` to superusers
  - Pop `restricted` for add view
  - Set `owner`/`parent` in clean method

#### 6f. `_move_files_and_folders_impl` — MPTT corruption
- **Problem:** Upstream used bulk `update()` which bypasses MPTT tree updates and model signals
- **Fix:** Changed to individual `save()` calls to trigger MPTT tree recalculation

#### 6g. `move_files_and_folders()` — PBS validation
- **Problem:** PBS site validation checks were missing from upstream's move implementation
- **Fix:** Restored:
  - Root folder move prevention
  - Site consistency checks (all moved items must belong to same site as destination)
- **Code:**
  ```python
  # PBS: prevent moving root folders
  if folders_queryset.filter(parent=None).exists():
      messages.error(request, "To prevent potential problems, users "
          "are not allowed to move root folders.")
      return
  # PBS: site consistency checks
  sites_from_folders = \
      set(folders_queryset.values_list('site_id', flat=True)) | \
      set(files_queryset.exclude(folder__isnull=True).\
              values_list('folder__site_id', flat=True))
  if sites_from_folders and None in sites_from_folders:
      messages.error(request, "Some of the selected files/folders "
          "do not belong to any site.")
      return
  ```

#### 6h. `log_deletion` deprecation
- **Problem:** Dead `else` branches for Django < 5.1; bug where `files_queryset` was logged instead of `folders_queryset`
- **Fix:** Removed dead branches, fixed queryset reference

### 7. `filer/server/backends/` — Server backend fixes (3 files)

- **Files:** `default.py`, `nginx.py`, `xsendfile.py`
- **Problem 1:** `filer_file.mime_type` — `filer_file` is a `FieldFile` (not the `File` model), so it has no `mime_type` attribute
- **Fix 1:** Added `mimetypes.guess_type()` fallback
- **Problem 2:** `file_obj=filer_file.file` — `filer_file` is already the `FieldFile`, `.file` is the raw Python file object
- **Fix 2:** Changed to `file_obj=filer_file`
- **Error:** `AttributeError: 'MultiStorageFieldFile' has no attribute 'mime_type'`

### 8. `filer/admin/views.py` — NewFolderForm missing `site` field

- **Problem:** Form only had `fields = ('name',)`, ignoring PBS `site` field from POST data
- **Fix:** Added `'site'` to form fields: `fields = ('name', 'site')`

### 9. `filer/templatetags/filermedia.py` — Deleted by upstream merge

- **Problem:** Upstream deleted `filermedia.py` but 8+ templates still reference `{% load filermedia %}`
- **Fix:** Restored file with `filer_staticmedia_prefix` simple tag
- **Error:** `TemplateSyntaxError: 'filermedia' is not a registered tag library`

### 10. `filer/admin/clipboardadmin.py` — Clipboard not created on upload

- **Problem:** Upstream commented out `Clipboard.objects.get_or_create(user=request.user)` in `ajax_upload`
- **Fix:** Restored the get_or_create call so clipboard is created during upload
- **Error:** `Clipboard.DoesNotExist`

### 11. `filer/tests/admin.py` — Test compatibility fixes

- **Clipboard access:** Replaced `self.superuser.filer_clipboard` with `Clipboard.objects.get(user=self.superuser)`
- **Return values:** Removed `return folders, files` from test methods

### 12. `filer/utils/cdn.py` — `modified_at` None guard

- **Problem:** `get_cdn_url()` crashes with `TypeError: unsupported operand type(s) for +: 'NoneType' and 'datetime.timedelta'` when `file_obj.modified_at` is `None`
- **Fix:** Added early return `if file_obj.modified_at is None: return url` before the timedelta arithmetic
- **Error:** `TypeError: unsupported operand type(s) for +: 'NoneType' and 'datetime.timedelta'`

---

## PBS-Specific Features Preserved

These features exist in the PBS fork but not in upstream django-filer:

| Feature | Description |
|---------|-------------|
| **Trash / Soft-delete** | Files/folders are soft-deleted to trash before permanent deletion |
| **Site-based permissions** | Folders belong to Django sites; users have site-scoped access |
| **Folder types** | `CORE_FOLDER`, `SITE_FOLDER` — restricts operations on system folders |
| **Restricted flag** | Files/folders can be marked restricted; cascades to children |
| **Shared folders** | M2M relationship allowing folders shared across sites |
| **CDN invalidation** | URL hashing and CDN cache invalidation on file changes |
| **S3/Botocore storage** | Multi-storage backend with S3 support |
| **Clipboard model** | Per-user clipboard for file operations |
| **Folder-affects-URL** | Hash-based filenames tied to folder structure |

---

## Test Results — ✅ All Passing

**Final result: 153 passed, 68 skipped, 0 failed** (matches PBS baseline)

All 59 previously failing tests have been resolved. The upstream merge is fully compatible with the PBS test suite.

---

## Files Modified (Summary)

| File | Type of Change |
|------|---------------|
| `setup.py` | Build fix (regex version reader) |
| `filer/__init__.py` | PEP 440 version fix |
| `filer/models/abstract.py` | Import guard for VILImage |
| `filer/admin/fileadmin.py` | Readonly fields fix |
| `filer/admin/folderadmin.py` | 8 separate fixes (AJAX view, move/copy validation, MPTT, field visibility) |
| `filer/admin/views.py` | NewFolderForm site field |
| `filer/admin/clipboardadmin.py` | Clipboard creation restored |
| `filer/server/backends/default.py` | mime_type + file_obj fixes |
| `filer/server/backends/nginx.py` | mime_type + file_obj fixes |
| `filer/server/backends/xsendfile.py` | mime_type + file_obj fixes |
| `filer/templatetags/filermedia.py` | Restored deleted file |
| `filer/templates/admin/filer/submit_line.html` | Delete URL pk guard |
| `filer/tests/admin.py` | Test compatibility fixes |
| `filer/utils/cdn.py` | `modified_at` None guard for CDN URL |
