from ondoc.tracking import models as track_models
import datetime
from ondoc.api.v1.utils import get_time_delta_in_minutes, aware_time_zone
from ipware import get_client_ip


class InitiateSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        visitor_id = request.session.get('visitor_id')
        visit_id = request.session.get('visit_id')
        last_visit_time = request.session.get('last_visit_time')

        if not visitor_id:
            visitor = track_models.Visitor.create_visitor()
            visitor_id = visitor.id
            request.session['visitor_id'] = visitor_id

        if not visit_id:
            client_ip, is_routable = get_client_ip(request)
            visit = track_models.Visits.create_visit(visitor_id, client_ip)
            request.session['visit_id'] = visit.id
            visit_time = aware_time_zone(visit.created_at)
            request.session['last_visit_time'] = datetime.datetime.strftime(visit_time, '%Y-%m-%d %H:%M:%S')

        if last_visit_time:
            get_time_diff = get_time_delta_in_minutes(last_visit_time)
            if int(get_time_diff) > 30:
                visit = track_models.Visits.create_visit(visitor_id)
                request.session['visit_id'] = visit.id
                visit_time = aware_time_zone(visit.created_at)
                request.session['last_visit_time'] = datetime.datetime.strftime(visit_time, '%Y-%m-%d %H:%M:%S')

        response = self.get_response(request)
        # Code to be executed for each request/response after
        # the view is called.

        return response

