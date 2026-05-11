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
    Invalidate the folder-listing cache for the given folder and its parent.

    Args:
        folder: A Folder instance, or None (for clipboard/unfiled files).
    """
    if folder is None:
        return

    folder_id = getattr(folder, 'pk', None) or getattr(folder, 'id', None)
    site_id = getattr(folder, 'site_id', None)

    if folder_id:
        key = FOLDER_LISTING_CACHE_KEY.format(
            site_id=site_id or '', folder_id=folder_id)
        cache.delete(key)
        logger.debug("Cache invalidated: %s", key)

    # Also invalidate the parent folder (its child list changed)
    parent = getattr(folder, 'parent', None)
    if parent:
        parent_id = getattr(parent, 'pk', None) or getattr(parent, 'id', None)
        parent_site_id = getattr(parent, 'site_id', site_id)
        if parent_id:
            parent_key = FOLDER_LISTING_CACHE_KEY.format(
                site_id=parent_site_id or '', folder_id=parent_id)
            cache.delete(parent_key)
            logger.debug("Cache invalidated (parent): %s", parent_key)

        # Also invalidate the grandparent folder
        grandparent = getattr(parent, 'parent', None)
        if grandparent:
            gp_id = getattr(grandparent, 'pk', None) or getattr(grandparent, 'id', None)
            gp_site_id = getattr(grandparent, 'site_id', parent_site_id)
            if gp_id:
                gp_key = FOLDER_LISTING_CACHE_KEY.format(
                    site_id=gp_site_id or '', folder_id=gp_id)
                cache.delete(gp_key)
                logger.debug("Cache invalidated (grandparent): %s", gp_key)


def invalidate_folder_listing_cache_for_file(file_obj):
    """
    Invalidate the folder-listing cache for the folder containing this file.

    Args:
        file_obj: A File instance.
    """
    folder = getattr(file_obj, 'folder', None)
    if folder:
        invalidate_folder_listing_cache(folder)

