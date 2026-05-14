#-*- coding: utf-8 -*-
from unittest.mock import patch, call

from django.test import TestCase, override_settings

from filer.utils.cache import (
    invalidate_folder_listing_cache,
    invalidate_folder_listing_cache_for_file,
    DEFAULT_FOLDER_LISTING_CACHE_KEY,
)


class MockFolder:
    """Lightweight folder stub to avoid DB hits."""
    def __init__(self, pk, site_id=None, parent=None):
        self.pk = pk
        self.id = pk
        self.site_id = site_id
        self.parent = parent
        self.parent_id = parent.pk if parent else None


class MockFile:
    """Lightweight file stub."""
    def __init__(self, folder=None):
        self.folder = folder


def _key(site_id, folder_id):
    return DEFAULT_FOLDER_LISTING_CACHE_KEY.format(
        site_id=site_id or '', folder_id=folder_id)


class TestInvalidateFolderListingCache(TestCase):

    @patch('filer.utils.cache.cache')
    def test_none_folder_is_noop(self, mock_cache):
        invalidate_folder_listing_cache(None)
        mock_cache.delete.assert_not_called()

    @patch('filer.utils.cache.cache')
    def test_virtual_folder_no_pk_is_noop(self, mock_cache):
        """FolderRoot / UnfiledImages have no pk."""
        class VirtualFolder:
            pass
        invalidate_folder_listing_cache(VirtualFolder())
        mock_cache.delete.assert_not_called()

    @patch('filer.utils.cache.cache')
    def test_virtual_folder_pk_none_is_noop(self, mock_cache):
        folder = MockFolder(pk=None)
        invalidate_folder_listing_cache(folder)
        mock_cache.delete.assert_not_called()

    @patch('filer.utils.cache.cache')
    def test_root_folder_with_site(self, mock_cache):
        """Root folder (no parent) with a site invalidates only itself."""
        folder = MockFolder(pk=10, site_id=3)
        invalidate_folder_listing_cache(folder)
        mock_cache.delete.assert_called_once_with(_key(3, 10))

    @patch('filer.utils.cache.cache')
    def test_root_folder_without_site(self, mock_cache):
        """Root folder with no site uses empty string in key."""
        folder = MockFolder(pk=10, site_id=None)
        invalidate_folder_listing_cache(folder)
        mock_cache.delete.assert_called_once_with(_key(None, 10))

    @patch('filer.utils.cache.cache')
    def test_child_folder_invalidates_self_and_parent(self, mock_cache):
        parent = MockFolder(pk=5, site_id=2)
        child = MockFolder(pk=15, site_id=2, parent=parent)
        invalidate_folder_listing_cache(child)
        mock_cache.delete.assert_has_calls([
            call(_key(2, 15)),
            call(_key(2, 5)),
        ])
        self.assertEqual(mock_cache.delete.call_count, 2)

    @patch('filer.utils.cache.cache')
    def test_grandchild_invalidates_self_parent_grandparent(self, mock_cache):
        grandparent = MockFolder(pk=1, site_id=7)
        parent = MockFolder(pk=5, site_id=7, parent=grandparent)
        child = MockFolder(pk=15, site_id=7, parent=parent)
        invalidate_folder_listing_cache(child)
        mock_cache.delete.assert_has_calls([
            call(_key(7, 15)),
            call(_key(7, 5)),
            call(_key(7, 1)),
        ])
        self.assertEqual(mock_cache.delete.call_count, 3)

    @patch('filer.utils.cache.cache')
    def test_parent_without_grandparent_stops_at_two_levels(self, mock_cache):
        parent = MockFolder(pk=5, site_id=2)
        child = MockFolder(pk=15, site_id=2, parent=parent)
        invalidate_folder_listing_cache(child)
        self.assertEqual(mock_cache.delete.call_count, 2)

    @patch('filer.utils.cache.cache')
    def test_site_less_folder_with_parent(self, mock_cache):
        """Folders with site_id=None format key with empty site."""
        parent = MockFolder(pk=1, site_id=None)
        child = MockFolder(pk=2, site_id=None, parent=parent)
        invalidate_folder_listing_cache(child)
        mock_cache.delete.assert_has_calls([
            call(_key(None, 2)),
            call(_key(None, 1)),
        ])

    @patch('filer.utils.cache.cache')
    def test_mixed_site_ids_in_hierarchy(self, mock_cache):
        """Each level uses its own site_id for the cache key."""
        grandparent = MockFolder(pk=1, site_id=10)
        parent = MockFolder(pk=5, site_id=20, parent=grandparent)
        child = MockFolder(pk=15, site_id=30, parent=parent)
        invalidate_folder_listing_cache(child)
        mock_cache.delete.assert_has_calls([
            call(_key(30, 15)),
            call(_key(20, 5)),
            call(_key(10, 1)),
        ])


class TestInvalidateFolderListingCacheForFile(TestCase):

    @patch('filer.utils.cache.cache')
    def test_file_with_folder(self, mock_cache):
        folder = MockFolder(pk=42, site_id=5)
        file_obj = MockFile(folder=folder)
        invalidate_folder_listing_cache_for_file(file_obj)
        mock_cache.delete.assert_called_once_with(_key(5, 42))

    @patch('filer.utils.cache.cache')
    def test_file_without_folder_is_noop(self, mock_cache):
        """Clipboard / unfiled files have folder=None."""
        file_obj = MockFile(folder=None)
        invalidate_folder_listing_cache_for_file(file_obj)
        mock_cache.delete.assert_not_called()

    @patch('filer.utils.cache.cache')
    def test_file_in_nested_folder_invalidates_ancestors(self, mock_cache):
        parent = MockFolder(pk=1, site_id=3)
        folder = MockFolder(pk=10, site_id=3, parent=parent)
        file_obj = MockFile(folder=folder)
        invalidate_folder_listing_cache_for_file(file_obj)
        mock_cache.delete.assert_has_calls([
            call(_key(3, 10)),
            call(_key(3, 1)),
        ])

