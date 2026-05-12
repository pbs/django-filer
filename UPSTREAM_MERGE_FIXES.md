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

- **Problem:** `__import__('filer').__version__` can fail because Django may not be installed in the build environment
- **Current PR state:** No `setup.py` remediation was merged in this PR; the file still imports the package for `__version__` and still retains the deprecated `setuptools.command.test` / `test_suite` / `tests_require` usage
- **Not yet applied:** Replace the import-based version lookup with a regex-based `get_version()` that reads `filer/__init__.py` without importing the package
- **Not yet applied:** Remove `cmdclass={'test': test}`, `test_suite`, and `tests_require` from `setup.py` when that file is updated in a future follow-up
- **Note:** The earlier version of this document incorrectly described these changes as already applied; this section now documents them as outstanding work only

### 2. `filer/__init__.py` — version note

- **Problem:** This fork ships `0.9.123`, so the previous note about changing `3.5.0.pbs.1` to `3.5.0+pbs.1` did not match the actual version in this PR
- **Fix:** Removed the incorrect PEP 440 migration note and documented the shipped fork version accurately

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

#### 14c. ~~Added `mime_type` model field~~ — **Reverted**
- **Original problem:** The PBS/Bento database has a `mime_type` NOT NULL column on `filer_file` (added by a Bento migration), but the filer `File` model had no corresponding field. Django's INSERT SQL omitted the column, causing `null value in column "mime_type" violates not-null constraint`
- **Original fix:** Added `mime_type` as a `CharField` on `File` model + migration `0008_add_mime_type_to_file.py`
- **Reverted because:** The migration didn't run in GHA CI (sqlite test DB was created without the column), causing 129 test failures with `no such column: filer_file.mime_type`. The `mime_type` column is managed by Bento-side migrations, not by django-filer — it should stay that way
- **Current status:** `mime_type` field and migration `0008` removed from filer. The Bento DB column remains managed by Bento's own migrations with its own DB-level default

### 15. Cache invalidation for folder listings (new feature)

- **Problem:** The `django_filer_rest` REST API caches folder listings with key `django_filer_rest.folder-listing:{site_id}:{folder_id}`. After file/folder operations (upload, move, copy, delete, restore, rename, restriction toggle), the cache was stale
- **Fix:** Created `filer/utils/cache.py` with `invalidate_folder_listing_cache()` and `invalidate_folder_listing_cache_for_file()` utilities. Wired cache invalidation into model methods:
  - `File.save()` — invalidates current folder + old folder (if file moved between folders)
  - `File.soft_delete()` — invalidates the folder the file was in
  - `File.restore()` — invalidates the folder the file was restored to
  - `Folder.save()` — invalidates the folder itself and its parent
  - `Folder.soft_delete()` — invalidates the folder and its parent
  - `Folder.restore()` — invalidates the folder and its parent
- **Note:** All invalidation uses inline imports to avoid circular import issues at module load time

### 16. `filer/admin/forms.py` — `_html_output` removed in Django 5.1

- **Problem:** `AsPWithHelpMixin.as_p_with_help()` called `self._html_output()` which was removed in Django 5.1 (`RemovedInDjango50Warning` → fully removed in 5.1)
- **Fix:** Rewrote `as_p_with_help()` to manually iterate `self.fields`, render each `BoundField` with label/field/errors/help_text using the same HTML structure
- **Error:** `AttributeError: 'CopyFilesAndFoldersForm' object has no attribute '_html_output'`

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
| `filer/models/filemodels.py` | Empty filename guard in `update_location_on_storage`, `storage.delete('')` guard, cache invalidation on save/delete/restore |
| `filer/models/foldermodels.py` | Cache invalidation on save/soft_delete/restore |
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
| `filer/utils/cache.py` | New file — folder listing cache invalidation utilities |
| `filer/admin/forms.py` | Replaced `_html_output` (removed in Django 5.1) in `AsPWithHelpMixin.as_p_with_help()` |
| `filer/tests/admin.py` | Test compatibility fixes |
