import os
import re

from setuptools import setup, find_packages


def get_version():
    """Read version from filer/__init__.py without importing the package."""
    init_py = os.path.join(os.path.dirname(__file__), 'filer', '__init__.py')
    with open(init_py) as f:
        match = re.search(r"^__version__\s*=\s*['\"]([^'\"]+)['\"]", f.read(), re.M)
    if not match:
        raise RuntimeError("Cannot find __version__ in filer/__init__.py")
    return match.group(1)


version = get_version()


def read(fname):
    """read the contents of a text file"""
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name='django-filer',
    version=version,
    url='http://github.com/stefanfoulis/django-filer',
    license='BSD',
    platforms=['OS Independent'],
    description='A file management application for django that makes handling of files and images a breeze.',
    long_description=read('README.rst'),
    author='Stefan Foulis',
    author_email='stefan.foulis@gmail.com',
    packages=find_packages(),
    python_requires='>=3.10',
    install_requires=(
        'django>=5.1,<5.2',
        'django-mptt>=0.6,<1.0',  # the exact version depends on Django
        'django_polymorphic>=4.0.0,<5.0',
        'django-js-asset>=2.0.0,<3.0',
        'easy-thumbnails>=2,<3.0',
        'Unidecode>=0.04,<1.2',
        'filetype',
        'pytz',
    ),
    extras_require={
        's3': [
            'boto3>=1.26,<2.0',
            'django-storages>=1.13,<2.0',
        ],
    },
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Framework :: Django',
        'Framework :: Django :: 5.1',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
        'Topic :: Internet :: WWW/HTTP',
    ],
)
