from ondoc.diagnostic.models import (LabTest, AvailableLabTest, Lab, LabAppointment, LabTiming, PromotedLab,
                                     CommonDiagnosticCondition, CommonTest)
from ondoc.ratings_review.models import (RatingsReview)
from ondoc.authentication.models import UserProfile, Address, User
from ondoc.doctor.models import (Doctor)
from rest_framework.viewsets import GenericViewSet
from rest_framework.response import Response
import json
from django.http import JsonResponse
from rest_framework import viewsets, mixins


class SubmitRatingViewSet(viewsets.GenericViewSet):

    def create(self, request):
        user_id = request.data.get('user')
        user_details = User.objects.get(id=user_id)
        rating = request.data.get('rating')
        review = request.data.get('review')
        profile = request.data.get('profile')
        concern_id = request.data.get('concern_id')
        resp={}
        if profile:
            try:
                if profile=='Doctor':
                    content_data = Doctor.objects.get(pk=concern_id)
                    rating_review = RatingsReview(user=user_details, ratings=rating, review=review,
                                                  content_object=content_data)
                    rating_review.save()
                else:
                    content_data = Lab.objects.get(pk=concern_id)
                    rating_review = RatingsReview(user=user_details, ratings=rating, review=review,
                                                  content_object=content_data)
                    rating_review.save()
                    resp['success'] = "Rating have been processed successfully!!"
            except Exception:
                resp['error'] = "Error Processing Rating Data!"

        response = JsonResponse(resp)
        return response
