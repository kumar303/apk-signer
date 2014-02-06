"""
A Django-Restframework adapter for Hawk

https://github.com/hueniverse/hawk

TODO: liberate
"""
import logging
import traceback

from django.conf import settings

from mohawk import Receiver
from mohawk.exc import HawkFail
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed


log = logging.getLogger(__name__)


class HawkAuthentication(BaseAuthentication):

    def authenticate(self, request):
        on_success = (DummyUser(), None)

        # In case there is an exception, tell others that the view passed
        # through Hawk authorization.
        request.hawk_receiver = None

        if getattr(settings, 'SKIP_HAWK_AUTH', False):
            log.warn('Hawk authentication disabled via settings')
            return on_success

        if not request.META.get('HTTP_AUTHORIZATION'):
            raise AuthenticationFailed('missing authorization header')

        try:
            receiver = Receiver(lookup_credentials,
                                request.META['HTTP_AUTHORIZATION'],
                                request.build_absolute_uri(),
                                request.method,
                                content=request.body,
                                content_type=request.META.get('CONTENT_TYPE'))
        except HawkFail, exc:
            log.debug(traceback.format_exc())
            log.info('Hawk: denying access because of '
                     '{exc.__class__.__name__}: {exc}'.format(exc=exc))
            raise AuthenticationFailed('authentication failed')

        # Pass our receiver object to the middleware so the request header
        # doesn't need to be parsed again.
        request.hawk_receiver = receiver
        return on_success


class DummyUser(object):
    pass


def lookup_credentials(cr_id):
    if cr_id not in settings.HAWK_CREDENTIALS:
        raise LookupError('No Hawk ID of {id}'.format(id=cr_id))
    return settings.HAWK_CREDENTIALS[cr_id]
