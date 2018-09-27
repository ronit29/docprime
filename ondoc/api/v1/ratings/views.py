from ondoc.diagnostic import models as lab_models
from ondoc.ratings_review.models import (RatingsReview)
from ondoc.authentication.models import UserProfile, Address, User
from ondoc.doctor import models as doc_models
from rest_framework.response import Response
from rest_framework import viewsets, mixins
from ondoc.authentication.backends import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from ondoc.api.v1.utils import IsConsumer
from .serializers import RatingBodySerializer
from .serializers import RatingDataSerializer


class SubmitRatingViewSet(viewsets.GenericViewSet):
    # authentication_classes = (JWTAuthentication, )
    # permission_classes = (IsAuthenticated, IsConsumer)

    def create(self, request):
        serializer = RatingBodySerializer(data= request.data)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data

        resp={}
        try:
            if valid_data.get('appointment_type') == RatingsReview.OPD:
                content_data = doc_models.OpdAppointment.objects.filter(id=valid_data.get('appointment_id')).first()
            else:
                content_data = lab_models.LabAppointment.objects.filter(id=valid_data.get('appointment_id')).first()
            if content_data:
                rating_review = RatingsReview(user=request.user, ratings=valid_data.get('rating'),
                                              appointment_type=valid_data.get('appointment_type'),
                                              appointment_id=valid_data.get('appointment_id'),
                                              review=valid_data.get('review'),
                                              content_object=content_data)
                rating_review.save()
                resp['success'] = "Rating have been processed successfully!!"
        except Exception as e:
            resp['error'] = e
        return Response(resp)


class GetRatingViewSet(viewsets.GenericViewSet):

    def get_ratings(self, request):
        serializer = RatingDataSerializer.get_ratings_data(request)
        resp={}
        resp['ratings'] = serializer
        return Response(resp)


