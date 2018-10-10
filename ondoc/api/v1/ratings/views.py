from ondoc.diagnostic import models as lab_models
from ondoc.ratings_review import models
from ondoc.ratings_review.models import (RatingsReview, ReviewCompliments)
from django.shortcuts import get_object_or_404
from ondoc.doctor import models as doc_models
from rest_framework.response import Response
from rest_framework import viewsets, mixins, status
from ondoc.authentication.backends import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from ondoc.api.v1.utils import IsConsumer
from . import serializers


class RatingsViewSet(viewsets.GenericViewSet):
    # authentication_classes = (JWTAuthentication,)
    # permission_classes = (IsAuthenticated, IsConsumer)


    def get_queryset(self):
        pass

    def create(self, request):
        serializer = serializers.RatingCreateBodySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data

        resp={}
        if valid_data.get('appointment_type') == RatingsReview.OPD:
            content_data = doc_models.OpdAppointment.objects.filter(id=valid_data.get('appointment_id')).first()
            if content_data and content_data.status == doc_models.OpdAppointment.COMPLETED:
                content_obj = content_data.doctor
        else:
            content_data = lab_models.LabAppointment.objects.filter(id=valid_data.get('appointment_id')).first()
            if content_data and content_data.status == lab_models.LabAppointment.COMPLETED:
                content_obj = content_data.lab
        if content_obj:
            try:
                rating_review = RatingsReview(user=request.user, ratings=valid_data.get('rating'),
                                              appointment_type=valid_data.get('appointment_type'),
                                              appointment_id=valid_data.get('appointment_id'),
                                              review=valid_data.get('review'),
                                              content_object=content_obj)
                rating_review.save()
                if valid_data.get('compliment'):
                    rating_review.compliment.add(*valid_data.get('compliment'))


            except Exception as e:
                resp['error'] = e
            resp['success'] = "Rating have been processed successfully!!"
        else:
            return Response({'error':'Object Not Found'}, status=status.HTTP_400_BAD_REQUEST)
        return Response(resp)

    def list(self, request):
        serializer = serializers.RatingListBodySerializerdata(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        if valid_data.get('content_type') == RatingsReview.OPD:
            content_data = doc_models.Doctor.objects.filter(id=valid_data.get('object_id')).first()
        else:
            content_data = lab_models.Lab.objects.filter(id=valid_data.get('object_id')).first()
        if content_data:
                ratings = content_data.get_ratings()
                body_serializer = serializers.RatingsModelSerializer(ratings, many=True, context={'request':request})
        else:
            return Response({'error': 'Invalid Object'}, status=status.HTTP_404_NOT_FOUND)
        return Response(body_serializer.data)

    def retrieve(self,request, pk):
        rating = get_object_or_404(RatingsReview, pk=pk)
        body_serializer = serializers.RatingsModelSerializer(rating, context={'request': request})
        return Response(body_serializer.data)

    def update(self, request, pk):

        rating = get_object_or_404(models.RatingsReview, pk=pk)

        serializer = serializers.RatingUpdateBodySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data





        resp={}

        rating.ratings = valid_data.get('rating')
        if valid_data.get('compliment'):
            rating.compliment.set(valid_data.get('compliment'))
        else:
            rating.compliment.set("")

        if valid_data.get('review'):
            rating.review = valid_data.get('review')
        # else:
        #     rating.review = ""
        rating.save()
        return Response({'msg': 'Sucessfully Updated'})







class GetComplementViewSet(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, IsConsumer)

    def get_complements(self, request):
        serializer = serializers.ReviewComplimentSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        type = valid_data.get('type')
        complement_data = ReviewCompliments.objects.filter(type=type).all()
        if type == ReviewCompliments.DOCTOR:
            body_serializer = serializers.GetComplementSerializer(complement_data, many=True, context={'request': request})
        elif type == ReviewCompliments.LAB:
            body_serializer = serializers.GetComplementSerializer(complement_data, many=True, context={'request': request})

        return Response(body_serializer.data)


