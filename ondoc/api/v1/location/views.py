from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from ondoc.location import models as location_models
from ondoc.doctor import models as doctor_models
from rest_framework import mixins, viewsets, status
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from . import serializers
from ondoc.api.v1.doctor.serializers import DoctorListSerializer
from ondoc.api.v1.doctor.serializers import DoctorProfileUserViewSerializer
from ondoc.api.pagination import paginate_queryset


class SearchUrlsViewSet(viewsets.GenericViewSet):

    def get_queryset(self):
        return location_models.EntityUrls.objects.filter(is_valid=True)

    @transaction.non_atomic_requests
    def list(self, request):
        response = {}
        searchUrl = request.GET.get('searchUrl', None)
        if not searchUrl:
            return Response({"error": "Missing Parameter: searchUrl"}, status=status.HTTP_400_BAD_REQUEST)

        related_entity_url_objs = self.get_queryset().filter(url=searchUrl)
        if len(related_entity_url_objs) != 1:
            return Response(response)
        else:
            related_entity_url_obj = related_entity_url_objs.first()
            if related_entity_url_obj.url_type == 'SEARCHURL':
                extra_info_dict = related_entity_url_obj.additional_info
                location_id = extra_info_dict.get('location_id', None)
                if not location_id:
                    return Response(response)

                location_dict = dict()
                location_address = location_models.EntityAddress.objects.get(id=location_id)
                if location_address.type == 'SUBLOCALITY':
                    city_location_address = location_models.EntityAddress.objects.get(id=location_address.parent)
                    location_dict['city'] = city_location_address.value
                    location_dict['locality'] = location_address.value
                else:
                    location_dict['city'] = location_address.value

                blueprints = location_models.EntityLocationRelationship.objects.filter(location_id=location_id)

                entities = list()
                for blueprint in blueprints:
                    if blueprint.content_type and blueprint.object_id:
                        ct = ContentType.objects.get_for_id(blueprint.content_type.id)
                        obj = ct.get_object_for_this_type(pk=blueprint.object_id)

                        if related_entity_url_obj.entity_type.upper() == 'DOCTOR':
                            associated_doctors = obj.assoc_doctors.all()
                            for doctor in associated_doctors:
                                if doctor.doctorpracticespecializations.all().filter(specialization__id=extra_info_dict['specialization_id']).exists():
                                    entities.append(doctor)

                entities_list = list()
                if related_entity_url_obj.entity_type.upper() == 'DOCTOR':
                    entities_list = DoctorListSerializer(entities, many=True, context={'request': request}).data

                response = {
                    'entity_type': related_entity_url_obj.entity_type.upper(),
                    'entity_list': entities_list,
                    'location': location_dict
                }

        return Response(response)

    @transaction.non_atomic_requests
    def retrieve(self, request):
        response = {}
        serializer = serializers.EntityDetailSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        entity_url = serializer.validated_data.get('pageUrl')
        if self.get_queryset().filter(url=entity_url, url_type='PAGEURL').exists():
            entity_url_obj = self.get_queryset().filter(url=entity_url, url_type='PAGEURL').first()
            entity_id = entity_url_obj.entity_id
            if entity_url_obj.entity_type.upper() == 'DOCTOR':
               entity = doctor_models.Doctor.objects.get(id=entity_id)
               response = DoctorProfileUserViewSerializer(entity, context={'request': request}).data

        return Response(response)
