from ondoc.diagnostic import models as lab_models
from ondoc.ratings_review import models
from django.db import transaction
from django.db.models import Q
from ondoc.ratings_review.models import (RatingsReview, ReviewCompliments)
from django.shortcuts import get_object_or_404
from ondoc.doctor import models as doc_models
from rest_framework.response import Response
from rest_framework import viewsets, mixins, status
from ondoc.authentication.backends import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from ondoc.api.v1.utils import IsConsumer, IsNotAgent
from . import serializers
from ondoc.api.v1.doctor import serializers as doc_serializers
from ondoc.api.v1.diagnostic import serializers as lab_serializers


class RatingsViewSet(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, IsConsumer, IsNotAgent)

    def get_queryset(self):
        return RatingsReview.objects.prefetch_related('compliment').filter(is_live=True)

    def prompt_close(self, request):
        serializer = serializers.RatingPromptCloseBodySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        resp = {}
        if valid_data.get('appointment_type') == RatingsReview.OPD:
            content_data = doc_models.OpdAppointment.objects.filter(id=valid_data.get('appointment_id')).first()
        else:
            content_data = lab_models.LabAppointment.objects.filter(id=valid_data.get('appointment_id')).first()
        try:
            content_data.rating_declined = True
            content_data.save()
            resp['success'] = 'Updated!'
        except Exception as e:
            return Response({'error': 'Something went wrong'}, status=status.HTTP_404_NOT_FOUND)
        return Response(resp)

    def create(self, request):
        serializer = serializers.RatingCreateBodySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data

        resp={}
        rating_review = None
        content_obj= None
        content_data = None

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
                with transaction.atomic():
                    rating_review = RatingsReview(user=request.user, ratings=valid_data.get('rating'),
                                                  appointment_type=valid_data.get('appointment_type'),
                                                  appointment_id=valid_data.get('appointment_id'),
                                                  # review=valid_data.get('review'),
                                                  content_object=content_obj)
                    rating_review.save()
                    content_data.is_rated = True
                    content_data.save()

                # if valid_data.get('compliment'):
                #     rating_review.compliment.add(*valid_data.get('compliment'))
            except Exception as e:
                return Response({'error': 'Something Went Wrong!'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            return Response({'status': 'success', 'id': rating_review.id if rating_review else None})
        else:
            return Response({'error': 'Object Not Found'}, status=status.HTTP_400_BAD_REQUEST)

    def list(self, request):
        serializer = serializers.RatingListBodySerializerdata(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        if valid_data.get('content_type') == RatingsReview.OPD:
            queryset = self.get_queryset().exclude(Q(review='') | Q(review=None))\
                                          .filter(doc_ratings__id=valid_data.get('object_id'))\
                                          .order_by('-updated_at')
            appointment = doc_models.OpdAppointment.objects.select_related('profile').filter(doctor_id=valid_data.get('object_id')).all()
        else:
            queryset = self.get_queryset().exclude(Q(review='') | Q(review=None))\
                                          .filter(lab_ratings__id=valid_data.get('object_id'))\
                                          .order_by('-updated_at')
            appointment = lab_models.LabAppointment.objects.select_related('profile').filter(lab_id=valid_data.get('object_id')).all()
        if len(queryset):
                body_serializer = serializers.RatingsModelSerializer(queryset, many=True, context={'request': request,
                                                                                                   'app': appointment})
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
            rating.compliment.set(valid_data.get('compliment'), clear=True)
        else:
            rating.compliment.set("")

        if valid_data.get('review'):
            rating.review = valid_data.get('review')
        rating.save()
        return Response({'success': 'Sucessfully Updated'})


    def unrated(self, request):
        user = request.user
        appntment = None
        resp = []

        opd_app = user.get_unrated_opd_appointment()
        lab_app = user.get_unrated_lab_appointment()

        if opd_app and lab_app:
            if opd_app.updated_at > lab_app.updated_at:
                appntment = doc_serializers.AppointmentRetrieveSerializer(opd_app, many=False, context={'request': request})
            else:
                appntment = lab_serializers.LabAppointmentRetrieveSerializer(lab_app, many=False, context={'request': request})
        elif opd_app and not lab_app:
            appntment = doc_serializers.AppointmentRetrieveSerializer(opd_app, many=False, context={'request': request})
        elif lab_app and not opd_app:
            appntment = lab_serializers.LabAppointmentRetrieveSerializer(lab_app, many=False, context={'request': request})
        else:
            resp = []
        if appntment:
            resp = appntment.data
        return Response(resp)



class GetComplementViewSet(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, IsConsumer)

    def get_complements(self, request):
        complement_data = ReviewCompliments.objects.all()
        body_serializer = serializers.GetComplementSerializer(complement_data, many=True, context={'request': request})

        return Response(body_serializer.data)


