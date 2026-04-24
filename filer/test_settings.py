# -*- coding: utf-8 -*-
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
    try:
        __import__(_app)
        INSTALLED_APPS.append(_app)
    except ImportError:
        pass

ROOT_URLCONF = 'filer.test_urls'
SITE_ID = 1
MEDIA_ROOT = os.path.abspath(os.path.join(TMP_ROOT, 'media'))
MEDIA_URL = '/media/'
STATIC_URL = '/static/'

USE_TZ = False  # because of a bug in easy-thumbnails 1.0.3

MIDDLEWARE = [
    'django.middleware.cache.UpdateCacheMiddleware',
    'django.middleware.common.CommonMiddleware',
    # 'django.contrib.sessions.middleware.SessionMiddleware',
    # 'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    # 'django.contrib.messages.middleware.MessageMiddleware',
]

try:
    import cms  # noqa: F401
    MIDDLEWARE.append('cms.middleware.user.CurrentUserMiddleware')
    CMS_TEMPLATES = [('cms_mock_template.html', 'cms_mock_template.html')]
    CMS_MODERATOR = True
    CMS_PERMISSION = True
except ImportError:
    pass

try:
    import sekizai  # noqa: F401
    SEKIZAI_IGNORE_VALIDATION = True
except ImportError:
    pass

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
try:
    import cms  # noqa: F401
    _ctx.append("cms.context_processors.media")
except ImportError:
    pass
try:
    import sekizai  # noqa: F401
    _ctx.append("sekizai.context_processors.sekizai")
except ImportError:
    pass

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
