import logging
from django import db
from django.conf import settings
from django.utils.decorators import decorator_from_middleware_with_args


class Routers(object):
    def __getattr__(self, name):
        for r in db.router.routers:
            if hasattr(r, name):
                return getattr(r, name)
        msg = 'Not found the router with the method "%s".' % name
        raise AttributeError(msg)


routers = Routers()
log = logging.getLogger(__name__)


class ReplicationMiddleware:
    def __init__(self, get_response=None, forced_state=None):
        self.get_response = get_response
        self.forced_state = forced_state

    def process_request(self, request):
        if self.forced_state is not None:
            state = self.forced_state
            #print('state by .forced_state attr: %s', state)
        else:
            state = 'default'
            #print('state by request method: %s', state)
        routers.set_state(state)

    def process_response(self, request, response):
        routers.reset()
        return response


use_state = decorator_from_middleware_with_args(ReplicationMiddleware)
use_default = use_slave = use_state(forced_state='default')
if settings.USE_SLAVE_DB:
    use_slave = use_state(forced_state='slave')
