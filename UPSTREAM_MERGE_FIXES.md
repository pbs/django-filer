# Upstream Merge Fix Progress

**Before this session:** 67 failed, 86 passed, 68 skipped  
**After this session:** 59 failed, 94 passed, 68 skipped (8 tests fixed)

## Fixes Applied

### 1. `setup.py` — Build-time import error (Fix for GHA)
- **Problem:** `__import__('filer').__version__` fails because Django isn't installed in the build environment
- **Fix:** Replaced with regex-based `get_version()` that reads `filer/__init__.py` without importing
- **Also:** Removed deprecated `setuptools.command.test` references

### 2. `filer/__init__.py` — PEP 440 version
- **Problem:** `3.5.0.pbs.1` is invalid per PEP 440
- **Fix:** Changed to `3.5.0+pbs.1` (local version identifier)

### 3. `filer/models/abstract.py` — VILImage import
- **Problem:** `from easy_thumbnails.VIL import Image` fails without `reportlab`
- **Fix:** Wrapped in try/except, set `VILImage = None` as fallback

### 4. `filer/admin/fileadmin.py` — `display_canonical` FieldError
- **Problem:** `get_readonly_fields` returned only model field names for restricted/core files, but fieldsets contain `display_canonical` (an admin method)
- **Fix:** Appended `'display_canonical'` to the readonly fields list in that code path

### 5. `filer/templates/admin/filer/submit_line.html` — Delete URL with empty pk
- **Problem:** `{% url opts|admin_urlname:'delete' obj.pk %}` failed when `obj.pk` was empty
- **Fix:** Changed to `original.pk` and added `and original.pk` guard

### 6. `filer/admin/folderadmin.py` — Multiple fixes
- **`destination_folders` AJAX view:** Added missing URL and view for the fancytree folder picker
- **`move_file_to_clipboard` signature:** Added missing `request` argument at both call sites
- **`KeyError: 'name'`:** Added guard `if 'name' not in cleaned_data: return cleaned_data`
- **`log_deletion` deprecation:** Removed dead `else` branches for Django < 5.1; fixed bug where `files_queryset` was logged instead of `folders_queryset`

### 7. `filer/server/backends/` — Server backend fixes
- **`default.py`, `nginx.py`, `xsendfile.py`:** Changed `filer_file.mime_type` to fallback using `mimetypes.guess_type()` since `filer_file` is a `FieldFile`, not the `File` model
- **All backends:** Changed `file_obj=filer_file.file` to `file_obj=filer_file` in `default_headers()` call — `filer_file` is already the `FieldFile`

### 8. `filer/admin/views.py` — NewFolderForm missing `site` field
- **Problem:** Form only had `fields = ('name',)`, ignoring `site` from POST data
- **Fix:** Added `'site'` to form fields

### 9. `filer/tests/admin.py` — Test fixes
- **Clipboard:** Replaced `self.superuser.filer_clipboard` with `Clipboard.objects.get(user=self.superuser)`
- **Return values:** Removed `return folders, files` from test methods (Python 3.12 deprecation)

---

## Remaining Failures (59 tests)

### Category 1: Clipboard/Upload (5 tests)
- `test_file_upload_no_duplicate_files`
- `test_filer_ajax_upload_long_filename`
- `test_filer_upload_image_no_extension`
- `test_paste_from_clipboard_no_duplicate_files`
- `test_move_to_clipboard_action`

**Root cause:** Upstream rewrote the upload flow. The `ajax_upload` view no longer truncates filenames, no longer auto-creates clipboards, and the clipboard model changed from `ForeignKey` to `OneToOneField`.

### Category 2: Folder Type Permissions (22 tests)
All `TestFolderTypePermissionForSuperUser` tests fail. These test PBS-specific folder type permissions (CORE_FOLDER, SITE_FOLDER), move/copy restrictions, clipboard operations.

**Root cause:** Upstream's `move_files_and_folders` and `copy_files_and_folders` lost PBS site-validation checks. The PBS permission model hooks (site mismatch, no-site, root folder prevention) were not preserved in the merge.

### Category 3: Folder Operations (6 tests)
- `TestFolderTypeFunctionality` (2)
- `TestMPTTCorruptionsOnFolderOperations` (3)
- `test_filer_make_root_folder_post`

**Root cause:** `make_folder` view changes, MPTT tree corruption, folder form validation.

### Category 4: File Validation (3 tests)
- `test_name_extension_change`
- `test_name_with_slash`
- `test_name_without_extension`

**Root cause:** Upstream added `validate_upload` with image size validation that PBS tests don't expect.

### Category 5: Image Change Form (2 tests)
- `test_image_change_data_only`
- `test_image_change_name_and_data`

**Root cause:** Upstream's `ImageAdmin` added new form validation and image processing.

### Category 6: Model Tests (8 tests)
- `test_cdn_urls`, `test_cdn_urls_no_timezone_support` — CDN URL format changed
- `test_credit_text_length_max_size` — Field length validation
- `test_slash_not_allowed_in_name` — `clean()` validation order
- `test_bulk_deleting_folder_deletes_all_files_from_filesystem` — File cleanup
- `ArchiveTest` (4) — Archive model attribute errors

### Category 7: Other (3 tests)
- `test_cascade_change_on_parent_restriction` — Restriction propagation
- `TestSharedFolderFunctionality` (3) — Shared folder M2M
- `test_restore_item_view` — Trash admin
- `test_thumbnails_removed_when_source_is_soft_deleted` — Thumbnail cleanup

---

## Recommended Next Steps

1. **Fix move/copy PBS validation hooks** in `folderadmin.py` `move_files_and_folders()` and `copy_files_and_folders()` — re-add site checks
2. **Restore filename truncation** in `ajax_upload` or update tests to match upstream behavior
3. **Fix Archive model** — ensure `archivemodels.py` is compatible with new `filemodels.py`
4. **Fix Image change form** — align `ImageAdmin` fieldsets with PBS model fields
5. **Fix CDN URL tests** — update to match current `canonical_url` property

