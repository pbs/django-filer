from django import forms
from django.db import models
from django.contrib.admin import widgets
from filer.utils.files import get_valid_filename
from django.utils.translation import gettext as _
from django.core.exceptions import ValidationError
from django.conf import settings


if 'cmsplugin_filer_image' in settings.INSTALLED_APPS:
    from cmsplugin_filer_image.models import ThumbnailOption


class AsPWithHelpMixin(object):
    def as_p_with_help(self):
        "Returns this form rendered as HTML <p>s with help text formatted for admin."
        from django.utils.html import conditional_escape
        from django.utils.safestring import mark_safe

        output = []
        for name in self.fields:
            bf = self[name]
            bf_errors = self.error_class(bf.errors)
            if bf_errors:
                output.append(str(bf_errors))
            css_classes = bf.css_classes()
            html_class_attr = ' class="%s"' % css_classes if css_classes else ''
            label = bf.label_tag() or ''
            field = str(bf)
            output.append('<p%s>%s %s</p>' % (html_class_attr, label, field))
            if bf.help_text:
                output.append('<p class="help">%s</p>' % conditional_escape(bf.help_text))
        return mark_safe('\n'.join(output))


class CopyFilesAndFoldersForm(forms.Form, AsPWithHelpMixin):
    suffix = forms.CharField(required=False, help_text=_("Suffix which will be appended to filenames of copied files."))
    # TODO: We have to find a way to overwrite files with different storage backends first.
    #overwrite_files = forms.BooleanField(required=False, help_text=_("Overwrite a file if there already exists a file with the same filename?"))

    def clean_suffix(self):
        valid = get_valid_filename(self.cleaned_data['suffix'])
        if valid != self.cleaned_data['suffix']:
            raise forms.ValidationError(_('Suffix should be a valid, simple and lowercase filename part, like "%(valid)s".') % {'valid': valid})
        return self.cleaned_data['suffix']


class RenameFilesForm(forms.Form, AsPWithHelpMixin):
    rename_format = forms.CharField(required=True)

    def clean_rename_format(self):
        try:
            self.cleaned_data['rename_format'] % {
                'original_filename': 'filename',
                'original_basename': 'basename',
                'original_extension': 'ext',
                'current_filename': 'filename',
                'current_basename': 'basename',
                'current_extension': 'ext',
                'current_folder': 'folder',
                'counter': 42,
                'global_counter': 42,
            }
        except KeyError as e:
            raise forms.ValidationError(_('Unknown rename format value key "%(key)s".') % {'key': e.args[0]})
        except Exception as e:
            raise forms.ValidationError(_('Invalid rename format: %(error)s.') % {'error': e})
        return self.cleaned_data['rename_format']


class ResizeImagesForm(forms.Form, AsPWithHelpMixin):
    if 'cmsplugin_filer_image' in settings.INSTALLED_APPS:
        thumbnail_option = models.ForeignKey(ThumbnailOption, null=True, blank=True, verbose_name=_("thumbnail option")).formfield()
    width = models.PositiveIntegerField(_("width"), null=True, blank=True).formfield(widget=widgets.AdminIntegerFieldWidget)
    height = models.PositiveIntegerField(_("height"), null=True, blank=True).formfield(widget=widgets.AdminIntegerFieldWidget)
    crop = models.BooleanField(_("crop"), default=True).formfield()
    upscale = models.BooleanField(_("upscale"), default=True).formfield()

    def clean(self):
        if not (self.cleaned_data.get('thumbnail_option') or ((self.cleaned_data.get('width') or 0) + (self.cleaned_data.get('height') or 0))):
            if 'cmsplugin_filer_image' in settings.INSTALLED_APPS:
                raise ValidationError(_('Thumbnail option or resize parameters must be choosen.'))
            else:
                raise ValidationError(_('Resize parameters must be choosen.'))
        return self.cleaned_data
