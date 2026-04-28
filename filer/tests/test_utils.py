#-*- coding: utf-8 -*-
from zipfile import ZipFile
import os

from django.core.files import File as DjangoFile
from django.test.testcases import TestCase
from filer.tests.helpers import create_image

from filer.utils.loader import load_object
from filer.utils.zip import unzip

#===============================================================================
# Some target classes for the classloading tests
#===============================================================================
class TestTargetSuperClass(object):
    pass

class TestTargetClass(TestTargetSuperClass):
    pass

#===============================================================================
# Testing the classloader
#===============================================================================
class ClassLoaderTestCase(TestCase):
    ''' Tests filer.utils.loader.load_object() '''

    def test_loader_loads_strings_properly(self):
        target = 'filer.tests.test_utils.TestTargetClass'
        result = load_object(target)
        self.assertEqual(result, TestTargetClass)

    def test_loader_returns_non_string_as_is(self):
        instance = TestTargetClass()
        result = load_object(instance)
        self.assertIs(result, instance)

    def test_loader_raises_on_no_dots(self):
        with self.assertRaises(TypeError):
            load_object('NoDots')

#===============================================================================
# Testing the zipping/unzipping of files
#===============================================================================

class ZippingTestCase(TestCase):

    def setUp(self):
        self.img = create_image()
        self.image_name = 'test_file.jpg'
        self.filename = os.path.join(os.path.dirname(__file__),
                                 self.image_name)
        self.img.save(self.filename, 'JPEG')

        self.file = DjangoFile(open(self.filename, 'rb'), name=self.image_name)

        self.zipfilename = 'test_zip.zip'

        self.zip = ZipFile(self.zipfilename, 'a')
        self.zip.write(self.filename)
        self.zip.close()

    def tearDown(self):
        # Clean up the created zip file
        os.remove(self.zipfilename)
        os.remove(self.filename)

    def test_unzipping_works(self):
        result = unzip(self.zipfilename)
        self.assertEqual(result[0][0].name, self.file.name)
