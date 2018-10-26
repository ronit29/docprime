from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django_extensions.db.fields import json

from ondoc.doctor.models import DoctorPracticeSpecialization, PracticeSpecialization
from ondoc.location import models as location_models
from ondoc.doctor import models as doctor_models
from rest_framework import mixins, viewsets, status
from django.shortcuts import get_object_or_404
from rest_framework.response import Response

from ondoc.location.models import CityInventory, EntityUrls
from . import serializers
from ondoc.api.v1.doctor.serializers import DoctorListSerializer
from ondoc.api.v1.doctor.serializers import DoctorProfileUserViewSerializer
from ondoc.api.pagination import paginate_queryset
from django.db.models import Q


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

    def list_cities(self, request):
        cities = CityInventory.objects.all().values('city')
        return Response(cities)

    def list_urls_by_city(self, request, city):
        if not city:
            return Response(status=status.HTTP_404_NOT_FOUND)

        entity = location_models.EntityUrls.objects.filter(locality_value__iexact=city, url_type='SEARCHURL',
                                                           entity_type__iexact='Doctor',
                                                           sitemap_identifier='SPECIALIZATION_CITY').order_by('-count')
        spec_city_urls = []
        for data in entity:
            title = None
            title = data.specialization + " in " + data.locality_value
            url = data.url
            count = data.count

            spec_city_urls.append(
                {
                    'title': title, 'url': url, 'count': count
                }
            )

        if spec_city_urls:
            urls_count = len(spec_city_urls)
            return Response({"specialization_city_urls": spec_city_urls, "list_size": urls_count})

        else:
            return Response(status=status.HTTP_404_NOT_FOUND)

    def specialists_list(self, request):
        specializations = PracticeSpecialization.objects.all()
        specialization_list = []
        for specialization in specializations:
            id = specialization.pk
            name = specialization.name
            specialization_list.append({"id": id, "specialization": name})

        return Response({"specialization-inventory": specialization_list})

    def specialities_in_localities_list(self, request, speciality):
        if not speciality:
            return Response(status=status.HTTP_404_NOT_FOUND)

        # entity = EntityUrls.objects.filter(id=579820)
        # # json_string =json.loads(entity.additional_info)
        # # entity.additional_info = entity.additional_info.replace("\'", "\"")
        # for data in entity:
        #     data.locality_value = data.locality_value.replace("\'", "\"")
        #     data.save()

        pages = None
        query = '''select * from 
                (select x.*, row_number() over(partition by locality order by count desc) row_num,
                 dense_rank() over(order by locality asc) city_num
                 from 
                (select specialization,url,count,extras,(extras->'location_json'->'locality_value')::TEXT as locality 
                 from entity_urls where url_type='SEARCHURL' and entity_type='Doctor'
                and sitemap_identifier = 'SPECIALIZATION_CITY' 
                )x)y where row_num<=20 and specialization  ~* '.*%s.*' order by city_num, row_num''' %(speciality)

        from ondoc.api.v1.utils import RawSql

        sql_urls = RawSql(query).fetch_all()

        # speciality_url = []
        #
        # for data in sql_urls:
        #     speciality_url.append(data.get('url'))

        pages = int(len(sql_urls)/500)
        if len(sql_urls) % 500 != 0:
            pages += 1

        paginated_specialists = self.paginate_sqlquery(query, pages)
        return Response({'paginated_specialists': paginated_specialists})

    def paginate_sqlquery(self, query, pages):
        from ondoc.api.v1.utils import RawSql
        query1 = '''%s  limit 500  offset 0''' % query
        page_size = 500
        speciality_urls_pages = []
        if pages==0:
            pages=pages+1
        while pages > 0:
            speciality_url = []

            if pages>1:
                offset = (pages - 1) * page_size
                query2 = '''%s limit 500  offset %d''' % (query, offset)
                sql_data_rest_pages = RawSql(query2).fetch_all()
                for data in sql_data_rest_pages:
                    speciality_url.append({"url": data.get('url')})

            else:
                sql_data_first_page = RawSql(query1).fetch_all()

                for data in sql_data_first_page:
                    speciality_url.append({"url": data.get('url')})

            speciality_urls_pages.append({"page":pages, "speciality_urls":speciality_url})

            pages = pages-1

        return speciality_urls_pages