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
| After Session 3 fixes | 0 | 153 | 68 |
| After Session 4 fixes (runtime) | 0 | 153 | 68 |

✅ **All 153 tests passing, 68 skipped**

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

### 4. `filer/admin/fileadmin.py` — `display_canonical` FieldError + readonly file display

- **Problem 1:** `get_readonly_fields` returned only model field names for restricted/core files, but fieldsets contain `display_canonical` (an admin method, not a model field)
- **Fix 1:** Appended `'display_canonical'` to the readonly fields list in that code path
- **Error:** `FieldError: Unknown field(s) (display_canonical) specified for File`
- **Problem 2:** The `submit-row` div with delete link still appeared for readonly/core files
- **Fix 2:** Added `is_readonly_file` context flag in `render_change_form` for files in core/readonly folders

### 5. `filer/templates/admin/filer/submit_line.html` — Delete URL with empty pk

- **Problem:** `{% url opts|admin_urlname:'delete' obj.pk %}` failed when `obj.pk` was empty
- **Fix:** Changed to `original.pk` and added `and original.pk` guard

### 6. `filer/admin/folderadmin.py` — Multiple fixes

#### 6a. `destination_folders` AJAX view
- **Problem:** `NoReverseMatch: 'filer-destination_folders' not found` — the fancytree folder picker widget needed this URL
- **Fix:** Added AJAX view and URL pattern to `FolderAdmin.get_urls()`; uses `self.get_queryset(request)` instead of raw `Folder.objects`; excludes core folders and orphaned folders (no site)

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
  - Removed early `AddFolderPopupForm` return when `parent_id` is set (was bypassing custom `clean` that sets parent/owner)

#### 6f. `_move_files_and_folders_impl` — MPTT corruption
- **Problem:** Upstream used bulk `update()` which bypasses MPTT tree updates and model signals
- **Fix:** Changed to individual `save()` calls to trigger MPTT tree recalculation

#### 6g. `move_files_and_folders()` — PBS validation
- **Problem:** PBS site validation checks were missing from upstream's move implementation
- **Fix:** Restored:
  - Root folder move prevention
  - Site consistency checks (all moved items must belong to same site as destination)
  - Core folder destination check
  - "No site" destination check

#### 6h. `log_deletion` deprecation
- **Problem:** Dead `else` branches for Django < 5.1; bug where `files_queryset` was logged instead of `folders_queryset`
- **Fix:** Removed dead branches, fixed queryset reference; added `log_deletions` helper method

#### 6i. `delete_view` — core folder deletion prevention
- **Problem:** Object-level `has_delete_permission` check was missing
- **Fix:** Added check to block core folder deletion via admin

#### 6j. `delete_files_or_folders` — permission check
- **Problem:** Missing `has_multi_file_action_permission` check
- **Fix:** Added check to block deletion of core/readonly folders in batch actions

#### 6k. `move_to_clipboard` — PBS behavior
- **Problem:** Upstream only moved files to clipboard, but permission checks were wrong
- **Fix:** Rewrote to match PBS behavior — only moves files (not folders), uses `has_multi_file_action_permission`, iterates `file_qs` instead of `folder_qs` for single-file moves

#### 6l. `copy_files_and_folders` — PBS validation
- **Problem:** Missing PBS site-validation checks
- **Fix:** Added core folder destination check and site consistency validation

#### 6m. `enable_restriction` / `disable_restriction` actions
- **Problem:** PBS restriction toggle actions were missing
- **Fix:** Added new action methods that toggle the `restricted` field with `has_multi_file_action_permission` gating

### 7. `filer/server/backends/` — Server backend fixes (3 files)

- **Files:** `default.py`, `nginx.py`, `xsendfile.py`
- **Problem 1:** `filer_file.mime_type` — `filer_file` is a `FieldFile` (not the `File` model), so it has no `mime_type` attribute
- **Fix 1:** Added `mimetypes.guess_type()` fallback
- **Problem 2:** `file_obj=filer_file.file` — `filer_file` is already the `FieldFile`, `.file` is the raw Python file object
- **Fix 2:** Changed to `file_obj=filer_file`
- **Error:** `AttributeError: 'MultiStorageFieldFile' has no attribute 'mime_type'`

### 8. `filer/admin/views.py` — Multiple fixes

#### 8a. NewFolderForm missing `site` field
- **Problem:** Form only had `fields = ('name',)`, ignoring PBS `site` field from POST data
- **Fix:** Added `'site'` to form fields: `fields = ('name', 'site')`

#### 8b. `make_folder` — parent not set before validation
- **Problem:** `Folder.clean()` needs parent set to run correctly for child folders
- **Fix:** Set parent on form instance before validation

#### 8c. `paste_clipboard_to_folder` — missing guards
- **Problem:** No handling for `None` folder_id, `Folder.DoesNotExist`, or invalid destinations
- **Fix:** Added guards for all three cases; uses `discard_clipboard_files` instead of `discard_clipboard` for partial moves

### 9. `filer/templatetags/filermedia.py` — Deleted by upstream merge

- **Problem:** Upstream deleted `filermedia.py` but 8+ templates still reference `{% load filermedia %}`
- **Fix:** Restored file with `filer_staticmedia_prefix` simple tag
- **Error:** `TemplateSyntaxError: 'filermedia' is not a registered tag library`

### 10. `filer/admin/clipboardadmin.py` — Multiple fixes

#### 10a. Clipboard not created on upload
- **Problem:** Upstream commented out `Clipboard.objects.get_or_create(user=request.user)` in `ajax_upload`
- **Fix:** Restored the get_or_create call so clipboard is created during upload
- **Error:** `Clipboard.DoesNotExist`

#### 10b. MIME type re-detection after filename truncation
- **Problem:** `truncate_filename` may add file extension via `filetype` library, but the upload's content type wasn't updated accordingly
- **Fix:** Re-detect MIME type after `truncate_filename` adds extension, fixing uploads without file extensions

### 11. `filer/tests/admin.py` — Test compatibility fixes

- **Clipboard access:** Replaced `self.superuser.filer_clipboard` with `Clipboard.objects.get(user=self.superuser)`
- **Return values:** Removed `return folders, files` from test methods

### 12. `filer/templates/admin/filer/file/change_form.html` — Readonly file template

- **Problem:** Submit row (with delete link) still appeared for files in core/readonly folders
- **Fix:** Added `submit_buttons_bottom` block override that suppresses the submit row when `is_readonly_file` is `True`

### 13. `filer/utils/cdn.py` — `modified_at` None guard

- **Problem:** `get_cdn_url()` crashed with `TypeError: unsupported operand type(s) for +: 'NoneType' and 'datetime.timedelta'` when `file_obj.modified_at` was `None`
- **Fix:** Added early return of plain URL when `modified_at` is `None`
- **Error:** `TypeError` in template rendering when accessing `.url` on files with null `modified_at`

### 14. `filer/models/filemodels.py` — Three runtime fixes

#### 14a. `update_location_on_storage` — empty filename on new file upload
- **Problem:** When `FOLDER_AFFECTS_URL` is enabled and a new file is uploaded, `_current_file_location` is `''`. Django 5.1's stricter `validate_file_name` rejects empty filenames with `SuspiciousFileOperation: Could not derive file name from ''`
- **Fix:** Added guard — when `_current_file_location` is empty, compute the target location via `upload_to` and save file content there directly
- **Error:** `SuspiciousFileOperation: Could not derive file name from ''`

#### 14b. `update_location_on_storage` — `storage.delete('')` on new files
- **Problem:** After saving, `old_location` was `''` and `storage.delete('')` was called, which Django 5.1 rejects with `ValueError: The name must be given to delete()`
- **Fix:** Added `old_location` truthiness check before both `storage.delete()` calls
- **Error:** `ValueError: The name must be given to delete().`

#### 14c. Auto-populate `mime_type` on save
- **Problem:** The PBS/Bento database has a `mime_type` NOT NULL column on `filer_file`, but filer's `save()` never sets it. Uploads via clipboard crash with `null value in column "mime_type" violates not-null constraint`
- **Fix:** Added auto-detection in `save()` — if the model has a `mime_type` attribute and it's empty, populate it from `original_filename` using `mimetypes.guess_type()`, defaulting to `application/octet-stream`
- **Code:**
  ```python
  if hasattr(self, 'mime_type') and not self.mime_type:
      import mimetypes
      filename = self.original_filename or (self.file.name if self.file else '')
      self.mime_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
  ```

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

## Files Modified (Summary)

| File | Type of Change |
|------|---------------|
| `setup.py` | Build fix (regex version reader) |
| `filer/__init__.py` | PEP 440 version fix |
| `filer/models/abstract.py` | Import guard for VILImage |
| `filer/models/filemodels.py` | Empty filename guard in `update_location_on_storage`, `storage.delete('')` guard, `mime_type` auto-populate |
| `filer/admin/fileadmin.py` | Readonly fields fix, `is_readonly_file` context flag |
| `filer/admin/folderadmin.py` | 13 separate fixes (AJAX view, move/copy validation, MPTT, field visibility, delete guards, restriction actions) |
| `filer/admin/views.py` | NewFolderForm site field, parent-before-validation, paste guards |
| `filer/admin/clipboardadmin.py` | Clipboard creation restored, MIME re-detection after truncation |
| `filer/server/backends/default.py` | mime_type + file_obj fixes |
| `filer/server/backends/nginx.py` | mime_type + file_obj fixes |
| `filer/server/backends/xsendfile.py` | mime_type + file_obj fixes |
| `filer/templatetags/filermedia.py` | Restored deleted file |
| `filer/templates/admin/filer/submit_line.html` | Delete URL pk guard |
| `filer/templates/admin/filer/file/change_form.html` | Suppress submit row for readonly files |
| `filer/utils/cdn.py` | `modified_at` None guard |
| `filer/tests/admin.py` | Test compatibility fixes |
