#-*- coding: utf-8 -*-
import os
from django.test import TestCase, RequestFactory
from django.core.urlresolvers import reverse
from django.core.exceptions import ValidationError
from django.core import files as dj_files
from django.contrib.admin import helpers, site
from django.contrib.sites.models import Site
from django.contrib.auth.models import User, Group, Permission
from django.http import HttpRequest
from filer.models.filemodels import File
from filer.models.archivemodels import Archive
from filer.models.foldermodels import Folder
from filer.models.imagemodels import Image
from filer.models.clipboardmodels import Clipboard
from filer.models.virtualitems import FolderRoot
from filer.models import tools
from filer.tests.helpers import (
    get_user_message, create_superuser, create_folder_structure,
    create_image, create_staffuser, create_folder_for_user, move_action,
    move_to_clipboard_action, paste_clipboard_to_folder, get_dir_listing_url,
    filer_obj_as_checkox, get_make_root_folder_url,
    move_single_file_to_clipboard_action,
)
from cmsroles.models import Role
from cmsroles.tests import HelpersMixin
from cmsroles.siteadmin import get_site_admin_required_permission


class FilerFolderAdminUrlsTests(TestCase):

    def setUp(self):
        self.superuser = create_superuser()
        self.client.login(username='admin', password='secret')

    def tearDown(self):
        self.client.logout()

    def test_filer_app_index_get(self):
        response = self.client.get(reverse('admin:app_list', args=('filer',)))
        self.assertEqual(response.status_code, 200)

    def test_filer_make_root_folder_get(self):
        response = self.client.get(get_make_root_folder_url() + "?_popup=1")
        self.assertEqual(response.status_code, 200)

    def test_filer_make_root_folder_post(self):
        FOLDER_NAME = "root folder 1"
        self.assertEqual(Folder.objects.count(), 0)
        data_to_post = {
             "name": FOLDER_NAME,
        }
        response = self.client.post(
            get_make_root_folder_url(),
            data_to_post)
        self.assertIn('Site is required', response.content)

        data_to_post['site'] = 1
        response = self.client.post(
            get_make_root_folder_url(),
            data_to_post)

        self.assertEqual(Folder.objects.count(), 1)
        self.assertEqual(Folder.objects.all()[0].name, FOLDER_NAME)
        self.assertEqual(response.status_code, 302)

    def test_filer_directory_listing_root_empty_get(self):
        response = self.client.get(get_dir_listing_url(None))
        self.assertEqual(response.status_code, 200)

    def test_filer_directory_listing_root_get(self):
        create_folder_structure(depth=3, sibling=2, parent=None)
        response = self.client.get(get_dir_listing_url(None))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['folder'].children.count(), 6)

    def test_validate_no_duplcate_folders(self):
        FOLDER_NAME = "root folder 1"
        self.assertEqual(Folder.objects.count(), 0)
        post_data = {"name": FOLDER_NAME, "_popup": 1}
        response = self.client.post(
            get_make_root_folder_url(),
            post_data)
        self.assertIn('Site is required', response.content)
        post_data['site'] = 1
        response = self.client.post(
            get_make_root_folder_url(),
            post_data)
        self.assertEqual(Folder.objects.count(), 1)
        self.assertEqual(Folder.objects.all()[0].name, FOLDER_NAME)
        # and create another one
        post_data = {"name": FOLDER_NAME, "_popup": 1}
        response = self.client.post(
            get_make_root_folder_url(),
            post_data)
        # second folder didn't get created
        self.assertEqual(Folder.objects.count(), 1)
        self.assertIn('File or folder with this name already exists',
                      response.content)

    def test_validate_no_duplcate_folders_on_rename(self):
        self.assertEqual(Folder.objects.count(), 0)
        post_data = {"name": "foo", "_popup": 1}
        response = self.client.post(
            get_make_root_folder_url(),
            post_data)
        self.assertIn('Site is required', response.content)
        post_data['site'] = 1
        response = self.client.post(
            get_make_root_folder_url(),
            post_data)

        self.assertEqual(Folder.objects.count(), 1)
        self.assertEqual(Folder.objects.all()[0].name, "foo")
        # and create another one
        post_data = {"name": "bar", "_popup": 1}
        response = self.client.post(
            get_make_root_folder_url(),
            post_data)
        self.assertIn('Site is required', response.content)

        post_data['site'] = 1
        response = self.client.post(
            get_make_root_folder_url(),
            post_data)

        self.assertEqual(Folder.objects.count(), 2)
        bar = Folder.objects.get(name="bar")
        response = self.client.post("/admin/filer/folder/%d/" % bar.pk, {
                "name": "foo",
                "_popup": 1})
        self.assertIn('File or folder with this name already exists',
                      response.content)
        # refresh from db and validate that it's name didn't change
        bar = Folder.objects.get(pk=bar.pk)
        self.assertEqual(bar.name, "bar")


class FilerImageAdminUrlsTests(TestCase):

    def setUp(self):
        self.superuser = create_superuser()
        self.client.login(username='admin', password='secret')

    def tearDown(self):
        self.client.logout()


class FilerClipboardAdminUrlsTests(TestCase):

    def setUp(self):
        self.superuser = create_superuser()
        self.client.login(username='admin', password='secret')
        self.img = create_image()
        self.image_name = 'test_file.jpg'
        self.filename = os.path.join(os.path.dirname(__file__),
                                 self.image_name)
        self.img.save(self.filename, 'JPEG')

    def tearDown(self):
        self.client.logout()
        os.remove(self.filename)
        for img in Image.objects.all():
            img.delete()

    def test_filer_upload_file(self, extra_headers={}):
        self.assertEqual(Image.objects.count(), 0)
        file_obj = dj_files.File(open(self.filename))
        response = self.client.post(
            reverse('admin:filer-ajax_upload'), {
            'Filename': self.image_name,
            'Filedata': file_obj,
            'jsessionid': self.client.session.session_key, },
            **extra_headers
        )
        self.assertEqual(Image.objects.count(), 1)
        self.assertEqual(Image.objects.all()[0].original_filename,
                         self.image_name)

    def test_file_upload_no_duplicate_files(self, extra_headers={}):
        self.assertEqual(Image.objects.count(), 0)
        file_obj = dj_files.File(open(self.filename))
        response = self.client.post(
            reverse('admin:filer-ajax_upload'), {
            'Filename': self.image_name,
            'Filedata': file_obj,
            'jsessionid': self.client.session.session_key, },
            **extra_headers
        )
        self.assertEqual(Image.objects.count(), 1)
        self.assertEqual(Image.objects.all()[0].original_filename,
                         self.image_name)
        # upload the same file again. This must fail since the
        # clipboard can't contain two files with the same name
        response = self.client.post(
            reverse('admin:filer-ajax_upload'), {
            'Filename': self.image_name,
            'Filedata': file_obj,
            'jsessionid': self.client.session.session_key, },
            **extra_headers
        )
        self.assertEqual(Image.objects.count(), 1)
        self.assertIn('error', response.content)

    def test_paste_from_clipboard_no_duplicate_files(self):
        first_folder = Folder.objects.create(name='first')

        def upload():
            file_obj = dj_files.File(open(self.filename))
            response = self.client.post(
                reverse('admin:filer-ajax_upload'),
                {'Filename': self.image_name, 'Filedata': file_obj,
                 'jsessionid': self.client.session.session_key, })
            return Image.objects.all().order_by('-id')[0]

        uploaded_image = upload()
        self.assertEqual(uploaded_image.original_filename, self.image_name)

        def paste(uploaded_image):
            # current user should have one clipboard created
            clipboard = self.superuser.filer_clipboards.all()[0]
            response = self.client.post(
                reverse('admin:filer-paste_clipboard_to_folder'),
                {'folder_id': first_folder.pk,
                 'clipboard_id': clipboard.pk})
            return Image.objects.get(pk=uploaded_image.pk)

        pasted_image = paste(uploaded_image)
        self.assertEqual(pasted_image.folder.pk, first_folder.pk)
        # upload and paste the same image again
        second_upload = upload()
        # second paste failed due to name conflict
        second_pasted_image = paste(second_upload)
        clipboard = self.superuser.filer_clipboards.all()[0]
        # file should remain in clipboard and should not be located in
        #   destination folder
        self.assertEqual(clipboard.files.count(), 1)
        self.assertEqual(second_pasted_image.folder, None)

    def test_filer_ajax_upload_file(self):
        self.assertEqual(Image.objects.count(), 0)
        file_obj = dj_files.File(open(self.filename))
        response = self.client.post(reverse('admin:filer-ajax_upload') +
            '?filename=%s' % self.image_name,
            data=file_obj.read(),
            content_type='application/octet-stream',
            **{'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}
        )
        self.assertEqual(Image.objects.count(), 1)
        self.assertEqual(Image.objects.all()[0].original_filename,
                         self.image_name)


class BulkOperationsMixin(object):

    def setUp(self):
        self.superuser = create_superuser()
        self.client.login(username='admin', password='secret')
        self.img = create_image()
        self.image_name = 'test_file.jpg'
        self.filename = os.path.join(os.path.dirname(__file__),
                                 self.image_name)
        self.img.save(self.filename, 'JPEG')
        self.create_src_and_dst_folders()
        self.folder = Folder.objects.create(name="root folder", parent=None)
        self.sub_folder1 = Folder.objects.create(
            name="sub folder 1", parent=self.folder)
        self.sub_folder2 = Folder.objects.create(
            name="sub folder 2", parent=self.folder)
        self.image_obj = self.create_image(self.src_folder)
        self.create_file(self.folder)
        self.create_file(self.folder)
        self.create_image(self.folder)
        self.create_image(self.sub_folder1)
        self.create_file(self.sub_folder1)
        self.create_file(self.sub_folder1)
        self.create_image(self.sub_folder2)
        self.create_image(self.sub_folder2)

    def tearDown(self):
        self.client.logout()
        os.remove(self.filename)
        for f in File.objects.all():
            f.delete()
        for folder in Folder.objects.all():
            folder.delete()

    def create_src_and_dst_folders(self):
        site = Site.objects.get(id=1)
        self.src_folder = Folder(name="Src", parent=None, site=site)
        self.src_folder.save()
        self.dst_folder = Folder(name="Dst", parent=None, site=site)
        self.dst_folder.save()

    def create_image(self, folder, filename=None):
        filename = filename or 'test_image.jpg'
        file_obj = dj_files.File(open(self.filename), name=filename)
        image_obj = Image.objects.create(
            owner=self.superuser, original_filename=self.image_name,
            file=file_obj, folder=folder)
        image_obj.save()
        return image_obj

    def create_file(self, folder, filename=None):
        filename = filename or 'test_file.dat'
        file_data = dj_files.base.ContentFile('some data')
        file_data.name = filename
        file_obj = File.objects.create(owner=self.superuser,
            original_filename=filename, file=file_data, folder=folder)
        file_obj.save()
        return file_obj


class FilerBulkOperationsTests(BulkOperationsMixin, TestCase):

    def test_move_files_and_folders_action(self):
        # TODO: Test recursive (files and folders tree) move

        self.assertEqual(self.src_folder.files.count(), 1)
        self.assertEqual(self.dst_folder.files.count(), 0)
        response, _ = move_action(
            self.client, self.src_folder, self.dst_folder, [self.image_obj])
        self.assertEqual(self.src_folder.files.count(), 0)
        self.assertEqual(self.dst_folder.files.count(), 1)

        response, _ = move_action(
            self.client, self.dst_folder, self.src_folder, [self.image_obj])
        self.assertEqual(self.src_folder.files.count(), 1)
        self.assertEqual(self.dst_folder.files.count(), 0)

    def test_validate_no_duplicate_folders_on_move(self):
        """ move file from foo to bar
          foo
          |--file
          bar
          |--file
        """
        foo = Folder.objects.create(name='foo', site=Site.objects.get(id=1))
        bar = Folder.objects.create(name='bar', site=Site.objects.get(id=1))
        file_foo = File.objects.create(
            original_filename='file', folder=foo,
            file=dj_files.base.ContentFile('some data'))
        file_bar = File.objects.create(
            original_filename='file', folder=bar,
            file=dj_files.base.ContentFile('some data'))

        response, url = move_action(
            self.client, foo, bar, [file_foo], follow=True)
        self.assertRedirects(response, url)
        self.assertIn(
            "already exist at the selected destination",
            get_user_message(response).message)

        foo = Folder.objects.get(id=foo.id)
        file_foo = File.objects.get(id=file_foo.id)
        self.assertEqual(foo.files.count(), 1)
        self.assertEqual(file_foo.parent.id, foo.id)

        bar = Folder.objects.get(id=bar.id)
        file_bar = File.objects.get(id=file_bar.id)
        self.assertEqual(bar.files.count(), 1)
        self.assertEqual(file_bar.parent.id, bar.id)

    def test_validate_no_duplicate_folders_on_move(self):
        """Create the following folder hierarchy:
        root
          |
          |--foo
          |   |-bar
          |
          |--bar

        and try to move the owter bar in foo. This has to fail since it
        would result in two folders with the same name and parent.
        """
        root = Folder.objects.create(name='root', owner=self.superuser)
        foo = Folder.objects.create(
            name='foo', parent=root, owner=self.superuser)
        bar = Folder.objects.create(
            name='bar', parent=root, owner=self.superuser)
        foos_bar = Folder.objects.create(
            name='bar', parent=foo, owner=self.superuser)
        url = get_dir_listing_url(root)

        response, _ = move_action(self.client, root, foo, [bar])
        # refresh from db and validate that it hasn't been moved
        bar = Folder.objects.get(pk=bar.pk)
        self.assertEqual(bar.parent.pk, root.pk)

    def test_move_to_clipboard_action(self):
        # TODO: Test recursive (files and folders tree) move

        self.assertEqual(self.src_folder.files.count(), 1)
        self.assertEqual(self.dst_folder.files.count(), 0)
        url = get_dir_listing_url(self.src_folder)
        response = move_to_clipboard_action(
            self.client, self.src_folder, [self.image_obj])
        self.assertEqual(self.src_folder.files.count(), 0)
        self.assertEqual(self.dst_folder.files.count(), 0)
        clipboard = Clipboard.objects.get(user=self.superuser)
        self.assertEqual(clipboard.files.count(), 1)
        request = HttpRequest()
        tools.move_files_from_clipboard_to_folder(
            request, clipboard, self.src_folder)
        tools.discard_clipboard(clipboard)
        self.assertEqual(clipboard.files.count(), 0)
        self.assertEqual(self.src_folder.files.count(), 1)

    def test_files_set_public_action(self):
        return
        self.image_obj.is_public = False
        self.image_obj.save()
        self.assertEqual(self.image_obj.is_public, False)
        url = get_dir_listing_url(self.src_folder)
        response = self.client.post(url, {
            'action': 'files_set_public',
            helpers.ACTION_CHECKBOX_NAME: 'file-%d' % (self.image_obj.id,),
        })
        self.image_obj = Image.objects.get(id=self.image_obj.id)
        self.assertEqual(self.image_obj.is_public, True)

    def test_files_set_private_action(self):
        return
        self.image_obj.is_public = True
        self.image_obj.save()
        self.assertEqual(self.image_obj.is_public, True)
        url = get_dir_listing_url(self.src_folder)
        response = self.client.post(url, {
            'action': 'files_set_private',
            helpers.ACTION_CHECKBOX_NAME: 'file-%d' % (self.image_obj.id,),
        })
        self.image_obj = Image.objects.get(id=self.image_obj.id)
        self.assertEqual(self.image_obj.is_public, False)
        self.image_obj.is_public = True
        self.image_obj.save()

    def test_copy_files_and_folders_action(self):
        # TODO: Test recursive (files and folders tree) copy

        self.assertEqual(self.src_folder.files.count(), 1)
        self.assertEqual(self.dst_folder.files.count(), 0)
        self.assertEqual(self.image_obj.original_filename, 'test_file.jpg')
        url = get_dir_listing_url(self.src_folder)
        response = self.client.post(url, {
            'action': 'copy_files_and_folders',
            'post': 'yes',
            'suffix': 'test',
            'destination': self.dst_folder.id,
            helpers.ACTION_CHECKBOX_NAME: 'file-%d' % (self.image_obj.id,),
        })
        self.assertEqual(self.src_folder.files.count(), 1)
        self.assertEqual(self.dst_folder.files.count(), 1)
        self.assertEqual(self.src_folder.files[0].id, self.image_obj.id)
        dst_image_obj = self.dst_folder.files[0]
        self.assertEqual(dst_image_obj.original_filename, 'test_filetest.jpg')


class FilerDeleteOperationTests(BulkOperationsMixin, TestCase):

    def test_delete_files_or_folders_action(self):
        self.assertNotEqual(File.objects.count(), 0)
        self.assertNotEqual(Image.objects.count(), 0)
        self.assertNotEqual(Folder.objects.count(), 0)
        url = get_dir_listing_url(None)
        folders = []
        for folder in FolderRoot().children.all():
            folders.append('folder-%d' % (folder.id,))
        response = self.client.post(url, {
            'action': 'delete_files_or_folders',
            'post': 'yes',
            helpers.ACTION_CHECKBOX_NAME: folders,
        })
        self.assertEqual(File.objects.count(), 0)
        self.assertEqual(Folder.objects.count(), 0)

    def test_delete_files_or_folders_action_with_mixed_types(self):
        # add more files/images so we can test the polymorphic queryset
        # with multiple types
        self.create_file(folder=self.src_folder)
        self.create_image(folder=self.src_folder)
        self.create_file(folder=self.src_folder)

        self.assertNotEqual(File.objects.count(), 0)
        self.assertNotEqual(Image.objects.count(), 0)
        url = get_dir_listing_url(self.folder)
        folders = []
        for f in File.objects.filter(folder=self.folder):
            folders.append('file-%d' % (f.id,))
        folders.append('folder-%d' % self.sub_folder1.id)
        response = self.client.post(url, {
            'action': 'delete_files_or_folders',
            'post': 'yes',
            helpers.ACTION_CHECKBOX_NAME: folders,
            })
        self.assertEqual(File.objects.filter(
            folder__in=[self.folder.id, self.sub_folder1.id]).count(), 0)


class FilerResizeOperationTests(BulkOperationsMixin, TestCase):

    def test_resize_images_action(self):
        # TODO: Test recursive (files and folders tree) processing
        self.assertEqual(self.image_obj.width, 800)
        self.assertEqual(self.image_obj.height, 600)
        # since the 'resize' action is disabled from the admin
        return
        url = get_dir_listing_url(self.src_folder.id)
        response = self.client.post(url, {
            'action': 'resize_images',
            'post': 'yes',
            'width': 42,
            'height': 42,
            'crop': True,
            'upscale': False,
            helpers.ACTION_CHECKBOX_NAME: 'file-%d' % (self.image_obj.id,),
        })
        self.image_obj = Image.objects.get(id=self.image_obj.id)
        self.assertEqual(self.image_obj.width, 42)
        self.assertEqual(self.image_obj.height, 42)


class BaseTestFolderTypePermissionLayer(object):

    def test_default_add_view_is_forbidden(self):
        response = self.client.get(reverse('admin:filer_folder_add'))
        self.assertEqual(response.status_code, 403)

    def test_change_child_site_folder(self):
        f1 = Folder.objects.create(name='foo', site=Site.objects.get(id=1))
        f2 = Folder.objects.create(name='foo_bar', parent=f1)
        # regular users should be able to change child folders
        response = self.client.get(
            reverse('admin:filer_folder_change', args=(f2.pk, )))
        self.assertEqual(response.status_code, 200)
        self.assertIn('adminform', response.context_data)
        # make sure the folder that is going to be saved is a site folder
        form = response.context_data['adminform'].form
        self.assertEqual(form.instance.folder_type, Folder.SITE_FOLDER)
        # only field 'name' should be visible
        self.assertItemsEqual(['name'], form.fields.keys())
        # check if save worked
        response = self.client.post(
            reverse('admin:filer_folder_change', args=(f2.pk, )), {
                'name': 'foo_bar__changed'
            })
        self.assertEqual(response.status_code, 302)
        f2__changed = Folder.objects.get(id=f2.pk)
        self.assertEqual(f2__changed.name, 'foo_bar__changed')
        self.assertEqual(f2__changed.folder_type, Folder.SITE_FOLDER)

    def test_add_core_folder(self):
        f1 = Folder.objects.create(
            name='foo', folder_type=Folder.CORE_FOLDER)
        f2 = Folder.objects.create(
            name='foo_bar', parent=f1, folder_type=Folder.CORE_FOLDER)
        self.assertEqual(f1.folder_type, Folder.CORE_FOLDER)
        self.assertEqual(f2.folder_type, Folder.CORE_FOLDER)
        url = get_make_root_folder_url()
        response = self.client.get(url,{
            'parent_id': f2.id
            })
        self.assertEqual(response.status_code, 403)

        response = self.client.post(url,{
            'parent_id': f2.id,
            'name': 'foo_bar_core'
            })
        self.assertEqual(response.status_code, 403)

    def test_change_core_folder(self):
        f1 = Folder.objects.create(
            name='foo', folder_type=Folder.CORE_FOLDER)
        f2 = Folder.objects.create(
            name='foo_bar', parent=f1, folder_type=Folder.CORE_FOLDER)
        self.assertEqual(f1.folder_type, Folder.CORE_FOLDER)
        self.assertEqual(f2.folder_type, Folder.CORE_FOLDER)
        # No one should be able to change core folders
        response = self.client.post(
            reverse('admin:filer_folder_change', args=(f2.pk, )),
            {'post': ['yes']})
        self.assertEqual(response.status_code, 403)
        response = self.client.post(
            reverse('admin:filer_folder_change', args=(f1.pk, )),
            {'post': ['yes']})
        self.assertEqual(response.status_code, 403)

    def test_delete_child_site_folder(self):
        f1 = Folder.objects.create(name='foo', site=Site.objects.get(id=1))
        f2 = Folder.objects.create(name='bar', parent=f1)
        f3 = Folder.objects.create(name='baz', parent=f1)
        # regular users should be able to delete child site folders
        response = self.client.post(
            reverse('admin:filer_folder_delete', args=(f2.pk, )),
            {'post': ['yes']})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Folder.objects.filter(id=f2.id).count(), 0)

        response = self.client.post(get_dir_listing_url(f1), {
                'action': 'delete_files_or_folders',
                'post': 'yes',
                helpers.ACTION_CHECKBOX_NAME: ['folder-%d' % f3.id],
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Folder.objects.filter(id=f3.id).count(), 0)

    def test_delete_child_core_folder(self):
        f1 = Folder.objects.create(name='foo')
        f2 = Folder.objects.create(
            name='bar', parent=f1, folder_type=Folder.CORE_FOLDER)
        f3 = Folder.objects.create(
            name='baz', parent=f1, folder_type=Folder.CORE_FOLDER)
        # regular users should not be able to delete child core folders
        response = self.client.post(
            reverse('admin:filer_folder_delete', args=(f2.pk, )),
            {'post': ['yes']})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Folder.objects.filter(id=f2.id).count(), 1)

        response = self.client.post(get_dir_listing_url(f1), {
                'action': 'delete_files_or_folders',
                'post': 'yes',
                helpers.ACTION_CHECKBOX_NAME: ['folder-%d' % f3.id],
        })
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Folder.objects.filter(id=f3.id).count(), 1)

    def test_add_root_folder(self):
        # superusers should be able to add only root site folders
        response = self.client.get(
            get_make_root_folder_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn('adminform', response.context_data)
        # make sure the folder that is going to be saved is a site folder
        form = response.context_data['adminform'].form
        self.assertEqual(form.instance.folder_type, Folder.SITE_FOLDER)
        # only fields 'site', 'name' should be visible
        self.assertItemsEqual(['site', 'name'], form.fields.keys())

        s1, _ = Site.objects.get_or_create(
            name='foo_site', domain='foo-domain.com')
        response = self.client.post(
            get_make_root_folder_url(),
            {'name': 'foo', 'site': s1.id})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Folder.objects.count(), 1)

    def test_change_root_core_folder(self):
        f1 = Folder.objects.create(
            name='foo', folder_type=Folder.CORE_FOLDER)
        response = self.client.get(
            reverse('admin:filer_folder_change', args=(f1.pk, )))
        self.assertEqual(response.status_code, 403)
        response = self.client.post(
            reverse('admin:filer_folder_change', args=(f1.pk, )), {})
        self.assertEqual(response.status_code, 403)

    def test_change_root_site_folder(self):
        f1 = Folder.objects.create(
            name='foo', folder_type=Folder.SITE_FOLDER)
        response = self.client.get(
            reverse('admin:filer_folder_change', args=(f1.pk, )))
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            reverse('admin:filer_folder_change', args=(f1.pk, )), {})
        self.assertEqual(response.status_code, 200)

    def test_delete_root_folder(self):
        f1 = Folder.objects.create(
            name='foo', folder_type=Folder.CORE_FOLDER)

        response = self.client.post(
            reverse('admin:filer_folder_delete', args=(f1.pk, )),
            {'post': 'yes'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Folder.objects.filter(id=f1.id).count(), 1)
        response = self.client.post(
            get_dir_listing_url(None), {
            'action': 'delete_files_or_folders',
            'post': 'yes',
            helpers.ACTION_CHECKBOX_NAME: ['folder-%d' % f1.id],
        })
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Folder.objects.filter(id=f1.id).count(), 1)

        Folder.objects.filter(id=f1.id).update(
            folder_type=Folder.SITE_FOLDER)
        response = self.client.post(
            reverse('admin:filer_folder_delete', args=(f1.pk, )),
            {'post': 'yes'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Folder.objects.filter(id=f1.id).count(), 0)
        f1 = Folder.objects.create(
            name='foo', folder_type=Folder.SITE_FOLDER)
        response = self.client.post(
            get_dir_listing_url(None), {
            'action': 'delete_files_or_folders',
            'post': 'yes',
            helpers.ACTION_CHECKBOX_NAME: ['folder-%d' % f1.id],
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Folder.objects.filter(id=f1.id).count(), 0)

    def _build_some_folder_structure(self, folder_type, site):
        _folders, _files = {}, {}
        foo1 = Folder.objects.create(
            name='foo1', folder_type=folder_type, site=site)
        _folders['foo1'] = foo1
        foo2 = Folder.objects.create(
            name='foo2', folder_type=folder_type, site=site)
        _folders['foo2'] = foo2
        bar = Folder.objects.create(
            name='bar', folder_type=folder_type, parent=foo1, site=site)
        _folders['bar'] = bar
        baz1 = Folder.objects.create(
            name='baz1', folder_type=folder_type, parent=bar, site=site)
        _folders['baz1'] = baz1
        baz2 = Folder.objects.create(
            name='baz2', folder_type=folder_type, parent=bar, site=site)
        _folders['baz2'] = baz2

        file_bar = File.objects.create(
            original_filename='bar_file', folder=bar,
            file=dj_files.base.ContentFile('some data'))
        _files['file_bar'] = file_bar
        return _folders, _files

    def test_move_core_folders(self):
        folders, files = self._build_some_folder_structure(
            Folder.CORE_FOLDER, None)

        response, _ = move_action(
            self.client, None, folders['foo2'], [folders['bar']])
        self.assertEqual(response.status_code, 403)

        response, _ = move_action(
            self.client, None, folders['foo2'], [folders['foo1']])
        self.assertEqual(response.status_code, 403)

    def test_move_site_folder_to_core_destination_folder(self):
        folders, files = self._build_some_folder_structure(
            Folder.SITE_FOLDER, Site.objects.get(id=1))
        f1 = Folder.objects.create(
            name='destination', folder_type=Folder.CORE_FOLDER)
        response, _ = move_action(self.client, None, f1, [folders['bar']])
        self.assertEqual(response.status_code, 403)
        f1.delete()
        return folders, files

    def _get_clipboard_files(self):
        clipboard, _ = Clipboard.objects.get_or_create(
            user=self.user)
        return clipboard.files

    def test_move_to_clipboard_from_root(self):
        file_foo = File.objects.create(
            original_filename='foo', folder=None,
            file=dj_files.base.ContentFile('some data'))
        self.assertEqual(
            self._get_clipboard_files().count(), 0)

        move_to_clipboard_action(self.client, 'unfiled', [file_foo])
        self.assertEqual(
            self._get_clipboard_files().count(), 1)

        file_bar = File.objects.create(
            original_filename='bar', folder=None,
            file=dj_files.base.ContentFile('some data'))
        move_single_file_to_clipboard_action(
            self.client, 'unfiled', [file_bar])
        self.assertEqual(
            self._get_clipboard_files().count(), 2)

    def test_move_to_clipboard_from_site_folders(self):
        foo = Folder.objects.create(name='foo', site=Site.objects.get(id=1))
        file_foo = File.objects.create(
            original_filename='foo', folder=foo,
            file=dj_files.base.ContentFile('some data'))
        self.assertEqual(
            self._get_clipboard_files().count(), 0)

        move_to_clipboard_action(self.client, None, [foo])
        self.assertEqual(
            self._get_clipboard_files().count(), 1)

        file_bar = File.objects.create(
            original_filename='bar', folder=foo,
            file=dj_files.base.ContentFile('some data'))
        move_to_clipboard_action(self.client, foo, [file_bar])
        self.assertEqual(
            self._get_clipboard_files().count(), 2)

        file_baz = File.objects.create(
            original_filename='baz', folder=foo,
            file=dj_files.base.ContentFile('some data'))
        move_single_file_to_clipboard_action(
            self.client, foo, [file_baz])
        self.assertEqual(
            self._get_clipboard_files().count(), 3)

    def test_move_to_clipboard_from_core_folders(self):
        foo = Folder.objects.create(name='foo',
                                    folder_type=Folder.CORE_FOLDER)
        file_foo = File.objects.create(
            original_filename='foo_file', folder=foo,
            file=dj_files.base.ContentFile('some data'))
        self.assertEqual(
            self._get_clipboard_files().count(), 0)
        response, _ = move_to_clipboard_action(self.client, None, [foo])
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            self._get_clipboard_files().count(), 0)
        response, _ = move_to_clipboard_action(self.client, foo, [file_foo])
        # actions are not available if current view is core folder
        self.assertEqual(
            self._get_clipboard_files().count(), 0)

        response = move_single_file_to_clipboard_action(
            self.client, foo, [file_foo])
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            self._get_clipboard_files().count(), 0)

    def test_move_from_clipboard_to_root(self):
        bar_file = File.objects.create(
            original_filename='bar_file',
            file=dj_files.base.ContentFile('some data'))
        clipboard, _ = Clipboard.objects.get_or_create(
            user=self.user)
        clipboard.append_file(bar_file)
        self.assertEqual(
            self._get_clipboard_files().count(), 1)
        response = paste_clipboard_to_folder(
            self.client, None, clipboard)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            self._get_clipboard_files().count(), 1)

    def test_move_from_clipboard_to_core_folders(self):
        bar_file = File.objects.create(
            original_filename='bar_file',
            file=dj_files.base.ContentFile('some data'))
        core_folder = Folder.objects.create(
            name='foo', folder_type=Folder.CORE_FOLDER)
        clipboard, _ = Clipboard.objects.get_or_create(
            user=self.user)
        clipboard.append_file(bar_file)
        self.assertEqual(
            self._get_clipboard_files().count(), 1)
        response = paste_clipboard_to_folder(
            self.client, core_folder, clipboard)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            self._get_clipboard_files().count(), 1)

    def test_move_from_clipboard_to_site_folders(self):
        bar_file = File.objects.create(
            original_filename='bar_file',
            file=dj_files.base.ContentFile('some data'))
        site_folder = Folder.objects.create(
            name='foo', site=Site.objects.get(id=1))
        clipboard, _ = Clipboard.objects.get_or_create(
            user=self.user)
        clipboard.append_file(bar_file)
        self.assertEqual(
            self._get_clipboard_files().count(), 1)
        response = paste_clipboard_to_folder(
            self.client, site_folder, clipboard)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            self._get_clipboard_files().count(), 0)
        self.assertEqual(len(site_folder.files), 1)

    def test_message_error_user_no_site_on_move(self):
        site = Site.objects.get(id=1)
        foo_root = Folder.objects.create(name='foo_root')
        foo = Folder.objects.create(name='foo', parent=foo_root)
        bar = Folder.objects.create(name='bar', site=site)
        response, url = move_action(
            self.client, foo_root, bar, [foo], follow=True)
        self.assertRedirects(response, url)
        self.assertIn(
            "Some of the selected files/folders do not belong to any site.",
            get_user_message(response).message)

    def test_message_error_user_sites_mismatch_on_move(self):
        site = Site.objects.get(id=1)
        other_site, _ = Site.objects.get_or_create(
            name='foo_site', domain='foo-domain.com')
        # make a root for foo in order to work for regular users
        foo_root = Folder.objects.create(name='foo_root', site=other_site)
        foo = Folder.objects.create(name='foo', parent=foo_root)
        bar = Folder.objects.create(name='bar11', site=site)
        url = get_dir_listing_url(foo_root)
        response, url = move_action(
            self.client, foo_root, bar, [foo], follow=True)
        self.assertRedirects(response, url)
        self.assertIn(
            "Selected files/folders need to belong to the same site as the "
            "destination folder.",
            get_user_message(response).message)

    def test_destination_no_site_on_move(self):
        site = Site.objects.get(id=1)
        foo = Folder.objects.create(name='foo')
        bar = Folder.objects.create(name='bar', site=site)
        baz = Folder.objects.create(name='baz', site=site, parent=bar)
        response, url = move_action(self.client, None, foo, [baz])
        assert response.status_code == 403

    def _test_folder_destination_filters_core_folders(self, action):
        foo = Folder.objects.create(
            name='foo', folder_type=Folder.CORE_FOLDER)
        bar = Folder.objects.create(
            name='bar', site=Site.objects.get(id=1))
        bar2 = Folder.objects.create(
            name='bar2', site=Site.objects.get(id=1))
        bar_file = File.objects.create(
            original_filename='bar_file',
            file=dj_files.base.ContentFile('some data'))

        url = get_dir_listing_url(bar)
        response = self.client.post(url, {
            'action': action,
            helpers.ACTION_CHECKBOX_NAME: [filer_obj_as_checkox(bar_file)]
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('destination_folders', response.context)
        dest_folders = response.context['destination_folders']
        self.assertNotIn(foo.id, [el[0].id for el in dest_folders])

    def test_move_destination_filters_core_folders(self):
        self._test_folder_destination_filters_core_folders(
            'move_files_and_folders')

    def test_move_from_unfiled(self):
        foo_file = File.objects.create(
            original_filename='foo_file',
            file=dj_files.base.ContentFile('some data'))
        bar = Folder.objects.create(
            name='bar', site=Site.objects.get(id=1))
        response, url = move_action(self.client, 'unfiled', bar, [foo_file])
        self.assertEqual(File.objects.filter(folder=bar).count(), 1)
        self.assertEqual(File.objects.filter(folder__isnull=True).count(), 0)

    def test_copy_destination_filters_restricted_folders(self):
        self._test_folder_destination_filters_core_folders(
            'copy_files_and_folders')

    def test_copy_site_folder_to_core_destination_folder(self):
        folders, files = self._build_some_folder_structure(
            Folder.SITE_FOLDER, Site.objects.get(id=1))
        f1 = Folder.objects.create(
            name='destination', folder_type=Folder.CORE_FOLDER)

        url = get_dir_listing_url(None)
        response = self.client.post(url, {
            'action': 'copy_files_and_folders',
            'post': 'yes',
            'destination': f1.id,
            helpers.ACTION_CHECKBOX_NAME:
                [filer_obj_as_checkox(folders['bar'])]})

        self.assertEqual(response.status_code, 403)
        return folders, files

    def test_file_from_core_folder_is_unchangeable(self):
        f1 = Folder.objects.create(name='foo', folder_type=Folder.CORE_FOLDER)
        file1 = File.objects.create(
            original_filename='bar_file', folder=f1,
            file=dj_files.base.ContentFile('some data'))
        url = reverse('admin:filer_file_change', args=(file1.id, ))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('submit', response.content)
        self.assertNotIn('delete/', response.content)
        # only one input(csrfmiddlewaretoken) the rest are readonly fields
        self.assertEqual(response.content.count('<input'), 1)

    def test_file_from_site_folder_is_changeable(self):
        f1 = Folder.objects.create(name='foo', site=Site.objects.get(id=1))
        file1 = File.objects.create(
            original_filename='bar_file', folder=f1,
            file=dj_files.base.ContentFile('some data'))
        url = reverse('admin:filer_file_change', args=(file1.id, ))
        response = self.client.get(url)
        self.assertIn('submit', response.content)
        self.assertIn('delete/', response.content)
        # at least the choose file and csrfmiddlewaretoken
        self.assertGreater(response.content.count('<input'), 2)

    def _build_files_structure_for_archive(self):
        file_structure = {}
        file_structure['foo'] = Folder.objects.create(
            name='foo', folder_type=Folder.CORE_FOLDER)
        file_structure['bar'] = Folder.objects.create(
            name='bar', site=Site.objects.get(id=1))
        file_structure['foo_file'] = Archive.objects.create(
            original_filename='foo_file.zip', folder=file_structure['foo'],
            file=dj_files.base.ContentFile('zippy'))
        file_structure['bar_file'] = Archive.objects.create(
            original_filename='bar_file.zip', folder=file_structure['bar'],
            file=dj_files.base.ContentFile('zippy'))
        file_structure['baz_file'] = Archive.objects.create(
            original_filename='baz_file.zip',
            file=dj_files.base.ContentFile('zippy'))
        return file_structure

    def test_extract_files_in_core_folder(self):
        files = self._build_files_structure_for_archive()
        url = get_dir_listing_url(files['foo'])
        assert Folder.objects.get(id=files['foo'].id).files.count() == 1
        response = self.client.post(url, {
            'action': 'extract_files',
            helpers.ACTION_CHECKBOX_NAME:
                [filer_obj_as_checkox(files['foo_file'])]})
        # will not get extracted since no actions available in core folders
        assert Folder.objects.get(id=files['foo'].id).files.count() == 1

    def test_extract_files_in_site_folder(self):
        files = self._build_files_structure_for_archive()
        url = get_dir_listing_url(files['bar'])
        response = self.client.post(url, {
            'action': 'extract_files',
            helpers.ACTION_CHECKBOX_NAME:
                [filer_obj_as_checkox(files['bar_file'])]}, follow=True)
        self.assertEqual(get_user_message(response).message,
                         'bar_file.zip is not a valid zip file')

    def test_extract_in_unfiled_folder(self):
        files = self._build_files_structure_for_archive()
        url = get_dir_listing_url('unfiled')
        count_in_unfiled = File.objects.filter(folder__isnull=True).count()
        response = self.client.post(url, {
            'action': 'extract_files',
            helpers.ACTION_CHECKBOX_NAME:
                [filer_obj_as_checkox(files['baz_file'])]})
        assert count_in_unfiled == File.objects.filter(
            folder__isnull=True).count()


class TestFolderTypePermissionForSuperUser(
    TestCase, BaseTestFolderTypePermissionLayer):

    def setUp(self):
        username = 'login_using_foo'
        password = 'secret'
        user = User.objects.create_user(username=username, password=password)
        user.is_superuser = user.is_staff = user.is_active = True
        user.save()
        user.user_permissions = Permission.objects.all()
        self.client.login(username=username, password=password)
        self.user = user


class TestFolderTypePermissionLayerForRegularUser(
    TestCase, BaseTestFolderTypePermissionLayer):

    def _user_setup(self, user):
        foo_base_group = Group.objects.create(name='foo_base_group')
        developer_role = Role.objects.create(
            name='foo_role', group=foo_base_group,
            is_site_wide=True)
        other_site, _ = Site.objects.get_or_create(
            name='foo_site', domain='foo-domain.com')
        developer_role.grant_to_user(user, Site.objects.get(id=1))
        developer_role.grant_to_user(user, other_site)

    def setUp(self):
        username = 'login_using_foo'
        password = 'secret'
        user = User.objects.create_user(username=username, password=password)
        user.is_staff = user.is_active = True
        user.save()
        filer_perms = Permission.objects.filter(
            content_type__app_label='filer')
        user.user_permissions = filer_perms
        self._user_setup(user)
        self.client.login(username=username, password=password)
        self.user = user

    def _make_user_site_admin(self):
        base_group = Group.objects.get(name='foo_base_group')
        base_group.permissions.add(get_site_admin_required_permission())

    def test_add_root_folder_for_site_admins(self):
        # site admins should be able to do this the same as superusers
        # add site admin perm to make the current user a site admin
        self._make_user_site_admin()
        self_cls = TestFolderTypePermissionLayerForRegularUser
        super(self_cls, self).test_add_root_folder()

    def test_add_root_folder(self):
        # regular users should not be able to add root folders at all
        response = self.client.get(
            get_make_root_folder_url())
        self.assertEqual(response.status_code, 403)
        response = self.client.post(
            get_make_root_folder_url(), {})
        self.assertEqual(response.status_code, 403)

    def test_change_root_site_folder(self):
        # regular users should not be able to change root folders at all
        f1 = Folder.objects.create(name='foo', folder_type=Folder.SITE_FOLDER)
        response = self.client.get(
            reverse('admin:filer_folder_change', args=(f1.pk, )))
        self.assertEqual(response.status_code, 403)
        response = self.client.post(
            reverse('admin:filer_folder_change', args=(f1.pk, )), {})
        self.assertEqual(response.status_code, 403)

    def test_delete_root_folder(self):
        f1 = Folder.objects.create(name='foo', site=Site.objects.get(id=1))
        # regular users should not be able to delete root folders at all
        for folder_type in [Folder.SITE_FOLDER, Folder.CORE_FOLDER]:
            Folder.objects.filter(id=f1.id).update(folder_type=folder_type)
            response = self.client.post(
                reverse('admin:filer_folder_delete', args=(f1.pk, )),
                {'post': 'yes'})
            self.assertEqual(response.status_code, 403)

            response = self.client.post(
                get_dir_listing_url(None), {
                'action': 'delete_files_or_folders',
                'post': 'yes',
                helpers.ACTION_CHECKBOX_NAME: ['folder-%d' % f1.id],
            })
            self.assertEqual(response.status_code, 403)
            # case when viewing another folder content
            # hit search and select a root folder to delete
            folder_for_view = Folder.objects.create(
                name='bar', site=Site.objects.get(id=1))
            response = self.client.post(
                get_dir_listing_url(folder_for_view), {
                'action': 'delete_files_or_folders',
                'post': 'yes',
                helpers.ACTION_CHECKBOX_NAME: ['folder-%d' % f1.id],
            })
            # this might be a bug since the folder requested for deletion
            #   is not passed to the delete_files_or_folders. For now
            #   just make sure it is not deleted
            self.assertEqual(response.status_code, 302)
            self.assertEqual(
                Folder.objects.filter(
                    id__in=[folder_for_view.id, f1.id]).count(), 2)

    def test_message_error_user_no_site_on_move_for_site_admins(self):
        self._make_user_site_admin()
        self.test_message_error_user_no_site_on_move()

    def test_message_error_user_no_site_on_move(self):
        site = Site.objects.get(id=1)
        foo_root = Folder.objects.create(name='foo_root')
        foo = Folder.objects.create(name='foo', parent=foo_root)
        bar = Folder.objects.create(name='bar', site=site)
        response, url = move_action(
            self.client, foo_root, bar, [foo])
        self.assertEqual(response.status_code, 403)

    def test_move_to_clipboard_from_site_folders_for_site_admins(self):
        self._make_user_site_admin()
        self_cls = TestFolderTypePermissionLayerForRegularUser
        super(self_cls, self).test_move_to_clipboard_from_site_folders()

    def test_move_to_clipboard_from_site_folders(self):
        foo = Folder.objects.create(name='foo', site=Site.objects.get(id=1))
        file_foo = File.objects.create(
            original_filename='foo', folder=foo,
            file=dj_files.base.ContentFile('some data'))
        self.assertEqual(
            self._get_clipboard_files().count(), 0)

        move_to_clipboard_action(self.client, None, [foo])
        self.assertEqual(
            self._get_clipboard_files().count(), 0)

        file_bar = File.objects.create(
            original_filename='bar', folder=foo,
            file=dj_files.base.ContentFile('some data'))
        move_to_clipboard_action(self.client, foo, [file_bar])
        self.assertEqual(
            self._get_clipboard_files().count(), 1)

        file_baz = File.objects.create(
            original_filename='baz', folder=foo,
            file=dj_files.base.ContentFile('some data'))
        move_single_file_to_clipboard_action(
            self.client, foo, [file_baz])
        self.assertEqual(
            self._get_clipboard_files().count(), 2)


class TestSiteFolderRoleFiltering(TestCase, HelpersMixin):

    def setUp(self):
        self._create_simple_setup()
        for user in User.objects.all():
            user.set_password('secret')
            user.save()
        self.foo_site = Site.objects.get(name='foo.site.com')
        self.bar_site = Site.objects.get(name='bar.site.com')
        self.folders, self.files = self._build_folder_structure()

    def get_listed_objects(self, folder, data={}):
        response = self.client.get(get_dir_listing_url(folder), data)
        try:
            items = response.context['paginator'].object_list
        except:
            items = []
        return response, items

    def _build_folder_structure(self):
        unfiled_file = File.objects.create(original_filename='unfiled_file',
            file=dj_files.base.ContentFile('some data'))
        foo = Folder.objects.create(name='foo', site=self.foo_site)
        foo_file = File.objects.create(original_filename='foo_file',
            file=dj_files.base.ContentFile('some data'), folder=foo)
        bar = Folder.objects.create(name='bar', site=self.bar_site)
        bar_file = File.objects.create(original_filename='bar_file',
            file=dj_files.base.ContentFile('some data'), folder=bar)
        none = Folder.objects.create(name='no_site')
        none_file = File.objects.create(original_filename='none_file',
            file=dj_files.base.ContentFile('some data'), folder=none)
        core = Folder.objects.create(
            name='core', folder_type=Folder.CORE_FOLDER)
        core_file = File.objects.create(original_filename='core_file',
            file=dj_files.base.ContentFile('some data'), folder=core)

        return {'foo': foo, 'bar': bar, 'none': none, 'core': core}, {
            'foo_file': foo_file,
            'bar_file': bar_file,
            'unfiled_file': unfiled_file,
            'core_file': core_file,
            'none_file': none_file}

    def test_search_for_site_admin(self):
        # jack is admin on bar site
        self.client.login(username='jack', password='secret')
        response, items = self.get_listed_objects(None, {'q': 'file'})
        expected = set([self.files['core_file'], self.files['none_file'],
                        self.files['bar_file'], self.files['unfiled_file']])
        assert expected <= set(items)
        assert self.files['foo_file'] not in items
        #unfiled present
        assert len(expected) + 1 <= len(items)

    def test_search_for_other_users(self):
        # bob is writer on bar site
        self.client.login(username='bob', password='secret')
        response, items = self.get_listed_objects(None, {'q': 'file'})
        expected = set([self.files['core_file'],
                        self.files['bar_file'], self.files['unfiled_file']])
        assert expected <= set(items)
        assert self.files['foo_file'] not in items
        assert self.files['none_file'] not in items
        #unfiled present
        assert len(expected) + 1 <= len(items)

    def test_search_for_multi_site_user(self):
        # joe is site admin for foo and bar
        self.client.login(username='joe', password='secret')
        response, items = self.get_listed_objects(None, {'q': 'file'})
        expected = set(self.files.values())
        assert expected <= set(items)
        #unfiled present
        assert len(expected) + 1 <= len(items)

    def test_dir_listing_for_site_admin(self):
        # jack is admin on bar site
        self.client.login(username='jack', password='secret')

        response, items = self.get_listed_objects(None)
        expected = set([
            self.folders['core'], self.folders['bar'], self.folders['none']])
        assert expected <= set(items)
        assert self.folders['foo'] not in items
        #unfiled folder present
        assert len(expected) + 1 == len(items)

        response, items = self.get_listed_objects('unfiled')
        assert [self.files['unfiled_file']] == items

        response, items = self.get_listed_objects(self.folders['core'])
        assert [self.files['core_file']] == items

        response, items = self.get_listed_objects(self.folders['foo'])
        assert response.status_code == 403

        response, items = self.get_listed_objects(self.folders['none'])
        assert [self.files['none_file']] == items

    def test_dir_listing_for_other_users(self):
        # bob is writer on bar site
        self.client.login(username='bob', password='secret')

        response, items = self.get_listed_objects(None)
        expected = set([self.folders['core'], self.folders['bar']])
        assert expected <= set(items)
        assert self.folders['foo'] not in items
        assert self.folders['none'] not in items
        #unfiled folder present
        assert len(expected) + 1 == len(items)

        response = self.client.get(get_dir_listing_url('unfiled'))
        items = response.context['paginator'].object_list
        assert [self.files['unfiled_file']] == items

        response, items = self.get_listed_objects(self.folders['core'])
        assert [self.files['core_file']] == items

        response, items = self.get_listed_objects(self.folders['foo'])
        assert response.status_code == 403

        response, items = self.get_listed_objects(self.folders['none'])
        assert response.status_code == 403

    def _test_destination_on_copy_for_site_admin(self, action):
        # joe is site admin for foo and bar
        self.client.login(username='joe', password='secret')
        url = get_dir_listing_url('unfiled')
        response = self.client.post(url, {
            'action': action,
            helpers.ACTION_CHECKBOX_NAME: [
                filer_obj_as_checkox(self.files['unfiled_file'])]
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('destination_folders', response.context)
        dest_folders = [_dest[0]
                        for _dest in response.context['destination_folders']]
        expected = set([self.folders['bar'], self.folders['foo']])
        assert expected == set(dest_folders)

    def _test_destination_action_for_multi_site_user(self, action):
        # bob will be a site admin on foo and writer on bar
        admin_role = Role.objects.get(name='site admin')
        admin_role.grant_to_user(
            User.objects.get(username='bob'), self.foo_site)
        self.client.login(username='bob', password='secret')
        url = get_dir_listing_url('unfiled')
        response = self.client.post(url, {
            'action': action,
            helpers.ACTION_CHECKBOX_NAME: [
                filer_obj_as_checkox(self.files['unfiled_file'])]
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('destination_folders', response.context)
        dest_folders = [_dest[0]
                        for _dest in response.context['destination_folders']]
        expected = set([self.folders['bar'], self.folders['foo']])
        assert expected == set(dest_folders)

    def _test_destination_action_for_other_users(self, action):
        # bob is writer on bar site
        self.client.login(username='bob', password='secret')
        url = get_dir_listing_url('unfiled')
        response = self.client.post(url, {
            'action': action,
            helpers.ACTION_CHECKBOX_NAME: [
                filer_obj_as_checkox(self.files['unfiled_file'])]
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('destination_folders', response.context)
        dest_folders = [_dest[0]
                        for _dest in response.context['destination_folders']]
        assert set([self.folders['bar']]) == set(dest_folders)

    def test_destination_on_copy_for_multi_site_user(self):
        self._test_destination_action_for_multi_site_user(
            'copy_files_and_folders')

    def test_destination_on_move_for_multi_site_user(self):
        self._test_destination_action_for_multi_site_user(
            'move_files_and_folders')

    def test_destination_on_copy_for_other_users(self):
        self._test_destination_action_for_other_users(
            'copy_files_and_folders')

    def test_destination_on_move_for_other_users(self):
        self._test_destination_action_for_other_users(
            'move_files_and_folders')

    def test_destination_on_copy_for_site_admin(self):
        self._test_destination_on_copy_for_site_admin(
            'copy_files_and_folders')

    def test_destination_on_move_for_site_admin(self):
        self._test_destination_on_copy_for_site_admin(
            'move_files_and_folders')

    def test_on_site_change_filtering(self):
        # jack is site admin on bar site
        self.client.login(username='jack', password='secret')
        response = self.client.get(
            reverse('admin:filer_folder_change',
                args=(self.folders['bar'].pk, )))
        self.assertEqual(response.status_code, 200)
        form = response.context_data['adminform'].form
        assert set([self.bar_site]) == set(form.fields['site'].queryset)
        self.client.logout()
        # bob is writer on bar
        self.client.login(username='bob', password='secret')
        response = self.client.get(
            reverse('admin:filer_folder_change',
                args=(self.folders['bar'].pk, )))
        self.assertEqual(response.status_code, 403)
        self.client.logout()
        # make bob a site admin on foo
        admin_role = Role.objects.get(name='site admin')
        admin_role.grant_to_user(
            User.objects.get(username='bob'), self.foo_site)
        # bob still doesn't have access on bar folder
        self.client.login(username='bob', password='secret')
        response = self.client.get(
            reverse('admin:filer_folder_change',
                args=(self.folders['bar'].pk, )))
        self.assertEqual(response.status_code, 403)
        # bob should have access on foo folder
        response = self.client.get(
            reverse('admin:filer_folder_change',
                args=(self.folders['foo'].pk, )))
        self.assertEqual(response.status_code, 200)
        form = response.context_data['adminform'].form
        assert set([self.foo_site]) == set(form.fields['site'].queryset)
        self.client.logout()
        # joe is multi site admin
        self.client.login(username='joe', password='secret')
        response = self.client.get(
            reverse('admin:filer_folder_change',
                args=(self.folders['bar'].pk, )))
        self.assertEqual(response.status_code, 200)
        form = response.context_data['adminform'].form
        expected = set([self.bar_site, self.foo_site])
        assert expected == set(form.fields['site'].queryset)
        self.client.logout()


class TestFolderTypeFunctionality(TestCase):

    def setUp(self):
        username = 'login_using_foo'
        password = 'secret'
        user = User.objects.create_user(username=username, password=password)
        user.is_superuser = user.is_staff = user.is_active = True
        user.save()
        self.client.login(username=username, password=password)
        self.user = user

    def test_owner_set_by_request_user_on_folder_form(self):
        response = self.client.post(
            get_make_root_folder_url(),
            {'name': 'foo', 'site': 1})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Folder.objects.count(), 1)
        self.assertEqual(Folder.objects.all()[0].owner, self.user)

    def test_make_folder_view_sets_parent_id_correctly(self):
        response = self.client.post(
            get_make_root_folder_url(),
            {'name': 'foo', 'site': 1, 'parent_id': ''})
        foo = Folder.objects.get(name='foo')
        self.assertEqual(foo.parent, None)
        response = self.client.post(
            get_make_root_folder_url(),
            {'name': 'bar', 'site': 1, 'parent_id': foo.id})
        bar = Folder.objects.get(name='bar')
        self.assertEqual(bar.parent_id, foo.id)

        response = self.client.post(
            reverse('admin:filer_folder_change', args=(bar.pk, )),
            {'post': ['yes'], 'name': 'baz'})
        self.assertEqual(response.status_code, 302)
        bar = Folder.objects.get(name='baz')
        self.assertEqual(bar.parent_id, foo.id)

    def test_folder_validation_works_on_model_and_form(self):
        foo = Folder(name='foo')
        foo.site_id = 1
        foo.save()

        bar = Folder(name='foo', site_id=1)
        with self.assertRaisesRegexp(ValidationError, 'name already exists'):
            bar.full_clean()
        bar.name = 'bar'
        bar.site = None
        with self.assertRaisesRegexp(ValidationError, 'Site is required'):
            bar.full_clean()
        bar.site = Site.objects.get(id=1)
        bar.folder_type = Folder.CORE_FOLDER
        with self.assertRaisesRegexp(ValidationError, 'Site must be empty.'):
            bar.full_clean()

        response = self.client.post(
            get_make_root_folder_url(),
            {'name': 'bar'})
        self.assertIn('Site is required', response.content)

        response = self.client.post(
            get_make_root_folder_url(),
            {'name': 'foo'})
        self.assertIn('name already exists', response.content)

    def test_folder_type_conversion_propagate_changes(self):
        site = Site.objects.get(id=1)
        foo = Folder.objects.create(name='foo', site=site)
        bar = Folder.objects.create(
            name='bar', site=site, parent=foo)
        foo.folder_type = Folder.CORE_FOLDER
        foo.save()
        foo = Folder.objects.get(name='foo')
        bar = Folder.objects.get(name='bar')
        self.assertEqual(foo.folder_type, Folder.CORE_FOLDER)
        self.assertEqual(foo.site, None)
        self.assertEqual(bar.folder_type, Folder.CORE_FOLDER)
        self.assertEqual(bar.site, None)
        foo.folder_type = Folder.SITE_FOLDER
        foo.site = site
        foo.save()
        foo = Folder.objects.get(name='foo')
        bar = Folder.objects.get(name='bar')
        self.assertEqual(foo.folder_type, Folder.SITE_FOLDER)
        self.assertEqual(foo.site, site)
        self.assertEqual(bar.folder_type, Folder.SITE_FOLDER)
        self.assertEqual(bar.site, site)
