import mimetypes

from django.http import HttpResponse

from .base import ServerBase


class ApacheXSendfileServer(ServerBase):
    def serve(self, request, filer_file, **kwargs):
        response = HttpResponse()
        response['X-Sendfile'] = filer_file.path

        # This is needed for lighttpd, hopefully this will
        # not be needed after this is fixed:
        # http://redmine.lighttpd.net/issues/2076
        response['Content-Type'] = getattr(filer_file, 'mime_type', None) or \
            mimetypes.guess_type(filer_file.path)[0] or 'application/octet-stream'

        self.default_headers(request=request, response=response, file_obj=filer_file, **kwargs)
        return response
