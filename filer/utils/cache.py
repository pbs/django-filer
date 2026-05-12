#-*- coding: utf-8 -*-
"""
Cache invalidation utilities for filer folder listings.

Invalidates the django_filer_rest folder-listing cache whenever
files or folders are added, moved, deleted, restored, or modified.
"""
import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)

FOLDER_LISTING_CACHE_KEY = 'django_filer_rest.folder-listing:{site_id}:{folder_id}'


def invalidate_folder_listing_cache(folder):
    """
    Invalidate the folder-listing cache for the given folder, its parent,
    and its grandparent.

    Args:
        folder: A Folder model instance or a virtual folder (FolderRoot,
                UnfiledImages). Virtual folders are ignored since they
                have no cache key.
    """
    if folder is None:
        return

    # Virtual folders (FolderRoot, UnfiledImages) don't have pk/site_id
    if not hasattr(folder, 'pk') or not folder.pk:
        return

    site_id = folder.site_id if hasattr(folder, 'site_id') else None

    key = FOLDER_LISTING_CACHE_KEY.format(
        site_id=site_id or '', folder_id=folder.pk)
    cache.delete(key)
    logger.debug("Cache invalidated: %s", key)

    # Also invalidate the parent folder (its child list changed)
    parent = folder.parent if hasattr(folder, 'parent') else None
    if parent:
        parent_key = FOLDER_LISTING_CACHE_KEY.format(
            site_id=parent.site_id or '', folder_id=parent.pk)
        cache.delete(parent_key)
        logger.debug("Cache invalidated (parent): %s", parent_key)

        # Also invalidate the grandparent folder
        if parent.parent_id:
            grandparent = parent.parent
            gp_key = FOLDER_LISTING_CACHE_KEY.format(
                site_id=grandparent.site_id or '', folder_id=grandparent.pk)
            cache.delete(gp_key)
            logger.debug("Cache invalidated (grandparent): %s", gp_key)


def invalidate_folder_listing_cache_for_file(file_obj):
    """
    Invalidate the folder-listing cache for the folder containing this file.

    Args:
        file_obj: A File model instance.
    """
    if file_obj.folder:
        invalidate_folder_listing_cache(file_obj.folder)

