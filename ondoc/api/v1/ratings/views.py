from ondoc.api.pagination import paginate_queryset
from ondoc.common.middleware import use_slave
from ondoc.diagnostic import models as lab_models
from ondoc.ratings_review import models
from django.db import transaction
from django.db.models import Q
from ondoc.ratings_review.models import (RatingsReview, ReviewCompliments, AppRatings, AppCompliments)
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

from ondoc.authentication.models import User
from django.contrib.contenttypes.models import ContentType
import logging
logger = logging.getLogger(__name__)



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
            if valid_data.get('appointment_id'):
                content_data = doc_models.OpdAppointment.objects.filter(id=valid_data.get('appointment_id')).first()
                if content_data and content_data.status == doc_models.OpdAppointment.COMPLETED:
                    content_obj = content_data.doctor
            else:
                content_obj = doc_models.Doctor.objects.filter(id=valid_data.get('entity_id')).first()
        elif valid_data.get('appointment_type') == RatingsReview.LAB:
            if valid_data.get('appointment_id'):
                content_data = lab_models.LabAppointment.objects.filter(id=valid_data.get('appointment_id')).first()
                if content_data and content_data.status == lab_models.LabAppointment.COMPLETED:
                    content_obj = content_data.lab
            else:
                content_obj = lab_models.Lab.objects.filter(id=valid_data.get('entity_id')).first()
        else:
            content_obj = doc_models.Hospital.objects.filter(id=valid_data.get('entity_id')).first()
        if content_obj:
            try:
                with transaction.atomic():
                    rating_review = RatingsReview(user=request.user, ratings=valid_data.get('rating'),
                                                  appointment_type=valid_data.get('appointment_type'),
                                                  appointment_id=valid_data.get('appointment_id', None),
                                                  is_live=True if valid_data.get('appointment_id') else False,
                                                  content_object=content_obj,
                                                  related_entity_id=valid_data.get('related_entity_id', None))
                    rating_review.save()
                    if valid_data.get('appointment_id'):
                        content_data.is_rated = True
                        content_data.save()

            except Exception as e:
                logger.error('Error Saving Appointment Rating ' + str(e))
                return Response({'error': 'Something Went Wrong!'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            return Response({'status': 'success', 'id': rating_review.id if rating_review else None})
        else:
            return Response({'error': 'Object Not Found'}, status=status.HTTP_400_BAD_REQUEST)

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

        rating.review = valid_data.get('review')
        rating.save()
        rating_obj = {}
        address = ''
        compliments_string= ''
        c_list = []
        cid_list = []
        appointment_id = rating.appointment_id
        if rating.content_type == ContentType.objects.get_for_model(doc_models.Doctor):
            name = rating.content_object.get_display_name()
            if appointment_id:
                appointment = doc_models.OpdAppointment.objects.select_related('hospital').filter(id=rating.appointment_id).first()
                if appointment:
                    address = appointment.hospital.get_hos_address()
        elif rating.content_type == ContentType.objects.get_for_model(lab_models.Lab):
            name = rating.content_object.name
            address = rating.content_object.get_lab_address()
        else:
            name = rating.content_object.name
            address = rating.content_object.get_hos_address()

        for cm in rating.compliment.all():
            c_list.append(cm.message)
            cid_list.append(cm.id)
        if c_list:
            compliments_string = (', ').join(c_list)
        rating_obj['id'] = rating.id
        rating_obj['ratings'] = rating.ratings
        rating_obj['address'] = address
        rating_obj['review'] = rating.review
        rating_obj['entity_name'] = name
        rating_obj['date'] = rating.updated_at.strftime('%b %d, %Y')
        rating_obj['compliments'] = compliments_string
        rating_obj['compliments_list'] = cid_list
        rating_obj['appointment_id'] = appointment_id
        rating_obj['entity_id'] = rating.object_id
        rating_obj['appointment_type'] = rating.appointment_type
        rating_obj['icon'] = request.build_absolute_uri(rating.content_object.get_thumbnail())
        return Response(rating_obj)


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


class AppRatingsViewSet(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, IsConsumer, IsNotAgent)

    def get_queryset(self):
        pass


    def create(self, request):
        serializer = serializers.AppRatingCreateBodySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        user = request.user
        try:
            with transaction.atomic():
                rating_obj = AppRatings(ratings=valid_data.get('rating'), review=valid_data.get('review'),
                                        user=user, app_type=AppRatings.CONSUMER, brand=valid_data.get('brand'),
                                        model=valid_data.get('model'), app_version=valid_data.get('app_version'),
                                        app_name=valid_data.get('app_name'), platform=valid_data.get('platform'),
                                        device_id=valid_data.get('device_id'))
                if valid_data.get('compliment'):
                    rating_obj.compliment.set(valid_data.get('compliment'), clear=True)
                rating_obj.save()
        except Exception as e:
            logger.error('Error Saving App Rating ' + str(e))
            return Response({'status': 'error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({'status': "success", "rating": rating_obj.id})


class ListRatingViewSet(viewsets.GenericViewSet):

    def get_queryset(self):
        return RatingsReview.objects.prefetch_related('compliment').filter(is_live=True)

    def get_opd_ratings(self, valid_data):
        queryset = self.get_queryset().exclude(Q(review='') | Q(review=None)) \
            .filter(doc_ratings__id=valid_data.get('object_id')) \
            .order_by('-updated_at')
        graph_queryset = self.get_queryset().filter(doc_ratings__id=valid_data.get('object_id'))
        appointment = doc_models.OpdAppointment.objects.select_related('profile').filter(
            doctor_id=valid_data.get('object_id')).all()
        return queryset, graph_queryset, appointment

    def get_lab_ratings(self, valid_data):
        lab = lab_models.Lab.objects.filter(id=valid_data.get('object_id')).first()
        if lab and lab.network:
            queryset = self.get_queryset().exclude(Q(review='') | Q(review=None)) \
                .filter(lab_ratings__network=lab.network) \
                .order_by('-updated_at')
            graph_queryset = self.get_queryset().filter(lab_ratings__network=lab.network)
            appointment = lab_models.LabAppointment.objects.select_related('profile').filter(
                lab__network=lab.network).all()
        else:
            queryset = self.get_queryset().exclude(Q(review='') | Q(review=None)) \
                .filter(lab_ratings__id=valid_data.get('object_id')) \
                .order_by('-updated_at')
            graph_queryset = self.get_queryset().filter(lab_ratings__id=valid_data.get('object_id'))
            appointment = lab_models.LabAppointment.objects.select_related('profile').filter(
                lab_id=valid_data.get('object_id')).all()
        return queryset, graph_queryset, appointment

    def get_hospital_ratings(self, valid_data):
        object_id = valid_data.get('object_id')
        hospital = doc_models.Hospital.objects.filter(id=object_id).first()
        appointment = []
        if hospital and hospital.network:
            queryset = self.get_queryset().exclude(Q(review='') | Q(review=None)) \
                .filter(Q(appointment_id__in=doc_models.OpdAppointment.objects.filter(hospital__network=hospital.network).values_list(
                                       'id', flat=True), appointment_type=RatingsReview.OPD) |
                        Q(related_entity_id=object_id, appointment_id__isnull=True)) \
                .order_by('-updated_at')
            graph_queryset = self.get_queryset().filter(Q(appointment_id__in=doc_models.OpdAppointment.objects.filter(hospital__network=hospital.network).values_list(
                                       'id', flat=True), appointment_type=RatingsReview.OPD) |
                        Q(related_entity_id=object_id, appointment_id__isnull=True)
                        )
        else:
            queryset = self.get_queryset().exclude(Q(review='') | Q(review=None)) \
                .filter(Q(appointment_id__in=doc_models.OpdAppointment.objects.filter(hospital_id=object_id).values_list(
                                       'id', flat=True), appointment_type=RatingsReview.OPD) |
                        Q(related_entity_id=object_id, appointment_id__isnull=True)
                        ) \
                .order_by('-updated_at')
            graph_queryset = self.get_queryset().filter(Q(appointment_id__in=doc_models.OpdAppointment.objects.filter(hospital_id=object_id).values_list(
                                       'id', flat=True), appointment_type=RatingsReview.OPD) |
                        Q(related_entity_id=object_id, appointment_id__isnull=True)
                        )

        return queryset, graph_queryset, appointment

    @use_slave
    def list(self, request):
        serializer = serializers.RatingListBodySerializerdata(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        if valid_data.get('content_type') == RatingsReview.OPD:
            queryset, graph_queryset, appointment = self.get_opd_ratings(valid_data)
        elif valid_data.get('content_type') == RatingsReview.LAB:
            queryset, graph_queryset, appointment = self.get_lab_ratings(valid_data)
        else:
            queryset, graph_queryset, appointment = self.get_hospital_ratings(valid_data)

        queryset = paginate_queryset(queryset, request)
        body_serializer = serializers.RatingsModelSerializer(queryset, many=True, context={'request': request,
                                                                                           'app': appointment})
        graph_serializer = serializers.RatingsGraphSerializer(graph_queryset,
                                                              context={'request': request})

        return Response({'rating': body_serializer.data,
                         'rating_graph': graph_serializer.data})

