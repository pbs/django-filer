# -*- coding: utf-8 -*-
import importlib.util
import os

import filer


DEBUG = True
PACKAGE_ROOT = os.path.abspath(os.path.join(
    os.path.dirname(filer.__file__), '..'))
TMP_ROOT = os.path.abspath(os.path.join(PACKAGE_ROOT, 'tmp'))
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(TMP_ROOT, 'filer_test.sqlite3'),
    },
}
INSTALLED_APPS = [
    'filer',
    'mptt',
    'easy_thumbnails',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sites',
    'django.contrib.admin',
    'django.contrib.sessions',
    'django.contrib.staticfiles',
]

# Optional CMS-related apps – only add them when they are actually installed.
_optional_apps = ['cms', 'menus', 'sekizai', 'cmsroles']
for _app in _optional_apps:
    if importlib.util.find_spec(_app) is not None:
        INSTALLED_APPS.append(_app)

ROOT_URLCONF = 'filer.test_urls'
SITE_ID = 1
MEDIA_ROOT = os.path.abspath(os.path.join(TMP_ROOT, 'media'))
MEDIA_URL = '/media/'
STATIC_URL = '/static/'

MIDDLEWARE = [
    'django.middleware.cache.UpdateCacheMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]

if importlib.util.find_spec('cms') is not None:
    MIDDLEWARE.append('cms.middleware.user.CurrentUserMiddleware')
    CMS_TEMPLATES = [('cms_mock_template.html', 'cms_mock_template.html')]
    CMS_MODERATOR = True
    CMS_PERMISSION = True

if importlib.util.find_spec('sekizai') is not None:
    SEKIZAI_IGNORE_VALIDATION = True

CACHE_BACKEND = 'locmem:///'

SECRET_KEY = 'secret'
TEST_RUNNER = 'django.test.runner.DiscoverRunner'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'OPTIONS': {
            'context_processors': [
                "django.contrib.auth.context_processors.auth",
                'django.contrib.messages.context_processors.messages',
                "django.template.context_processors.i18n",
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.template.context_processors.media",
                'django.template.context_processors.csrf',
                "django.template.context_processors.static",
            ],
            'loaders': (
                'filer.tests.utils.MockLoader',
                'django.template.loaders.filesystem.Loader',
                'django.template.loaders.app_directories.Loader',
            ),
            'debug': False
        },
    },
]

# Append optional CMS/sekizai context processors when available.
_ctx = TEMPLATES[0]['OPTIONS']['context_processors']
if importlib.util.find_spec('cms') is not None:
    _ctx.append("cms.context_processors.media")
if importlib.util.find_spec('sekizai') is not None:
    _ctx.append("sekizai.context_processors.sekizai")

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '%(levelname)s %(module)s %(message)s'
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },
    },
    'root': {
        'handlers': ['console', ],
        'level': 'WARNING',
    },
}
