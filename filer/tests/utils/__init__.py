from django.template.loaders.base import Loader as BaseLoader
from django.template import Origin
from django.template.exceptions import TemplateDoesNotExist


class Mock():
    pass


class MockLoader(BaseLoader):

    is_usable = True

    _templates = {
        'cms_mock_template.html': '<div></div>',
        '404.html': '404 Not Found',
    }

    def get_template_sources(self, template_name):
        if template_name in self._templates:
            yield Origin(
                name=template_name,
                template_name=template_name,
                loader=self,
            )

    def get_contents(self, origin):
        try:
            return self._templates[origin.template_name]
        except KeyError:
            raise TemplateDoesNotExist(origin)
