from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.geos import GEOSGeometry
from django.db import transaction
from django_extensions.db.fields import json
from ondoc.doctor.models import DoctorPracticeSpecialization, PracticeSpecialization
from ondoc.location import models as location_models
from ondoc.doctor import models as doctor_models
from rest_framework import mixins, viewsets, status
from django.shortcuts import get_object_or_404
from rest_framework.response import Response

from ondoc.location.models import CityInventory, EntityUrls, EntityAddress
from . import serializers
from ondoc.api.v1.doctor.serializers import DoctorListSerializer
from ondoc.api.v1.doctor.serializers import DoctorProfileUserViewSerializer
from ondoc.api.v1.utils import RawSql


import logging

logger = logging.getLogger(__name__)


class Footer(object):
    def get_urls(self, query, parameters):
        sql_urls = RawSql(query, parameters).fetch_all()
        return sql_urls


class LabProfileFooter(Footer):
    def __init__(self, entity):
        self.sublocality_id = int(entity.sublocality_id) if entity.sublocality_id else None
        self.locality_id = int(entity.locality_id) if entity.locality_id else None
        self.sublocality = entity.sublocality_value
        self.locality = entity.locality_value
        self.sublocality_location = entity.sublocality_location
        self.centroid = entity.location

        # location_id = int(entity.extras.get('location_id'))
        # address = EntityAddress.objects.filter(pk=location_id)
        # if address:
        #     address = address[0]
        #
        # if address:
        #     self.centroid = address.centroid
        #
        #     if address.type_blueprint=='SUBLOCALITY':
        #         self.sublocality_id = address.id
        #         self.sublocality = address.alternative_value
                # address = EntityAddress.objects.filter(pk=address.parent)
                # if len(address)>0:
                #     address = address[0]
                #     self.locality_id = address.id
                #     self.locality= address.alternative_value
            #
            #
            # else:
            #     self.locality_id = address.id
            #     self.locality = address.alternative_value

    def get_footer(self):
        response = {}
        response['menu'] = []
        labs_in_same_locality = []

        if self.locality and self.centroid:
            labs_in_same_locality = self.labs_in_same_locality()
            if labs_in_same_locality:
                response['menu'].append(
                    {'sub_heading': 'Other labs in same or nearby localities', 'url_list':labs_in_same_locality})

        if self.locality and self.centroid:
            labs_in_nearby_localities = self.labs_in_nearby_localities()
            if labs_in_nearby_localities:
                response['menu'].append(
                    {'sub_heading':'Labs in Nearby Localities','url_list':labs_in_nearby_localities})

        if self.centroid:
            popular_labs_in_city = self.popular_labs_in_city(labs_in_same_locality)
            if popular_labs_in_city:
                response['menu'].append(
                    {'sub_heading':'Popular Labs in City','url_list':popular_labs_in_city})


        return response

    def labs_in_same_locality(self):
           query = '''select eu.url, lb.name, concat(lb.name ) title from entity_urls eu inner join 
                        lab lb on eu.entity_id = lb.id
                        and eu.sitemap_identifier = 'LAB_PAGE' and lower(eu.locality_value) = lower(%s) and ST_DWithin(eu.location, %s, 20000)
                        and eu.is_valid = True 
                        order by st_distance(eu.location, %s) asc limit 10
                        '''

           return self.get_urls(query,[self.locality, self.centroid.ewkt, self.centroid.ewkt])

    def labs_in_nearby_localities(self):
        query = '''select eu.url, concat('Labs in ', sublocality_value,' ', locality_value) title from entity_urls eu where 
                    sitemap_identifier = 'LAB_LOCALITY_CITY'and is_valid = True and locality_value = %s and ST_DWithin(sublocality_location, %s, 20000) 
                    order by count desc limit 10'''

        return self.get_urls(query, [self.locality, self.centroid.ewkt])

    def popular_labs_in_city(self, labs_in_same_locality):
        result = []
        urls_nearby_labs = [lab_url['url'] for lab_url in labs_in_same_locality if 'url' in lab_url]
        # query = '''select a.url, a.title from
        #               (
        #         select url, lb.name title,
        #         row_number() over (partition by ln.id order by st_distance(lb.location, %s) ASC) as row_number
        #         from entity_urls eu inner join lab lb on eu.entity_id = lb.id and eu.sitemap_identifier = 'LAB_PAGE' and
        #         eu.is_valid = True  and eu.locality_value ilike %s and
        #         ST_DWithin(lb.location, %s, 20000)
        #         inner join seo_lab_network sln on lb.network_id = sln.lab_network_id
        #         inner join lab_network ln on ln.id=sln.lab_network_id  order by rank
        #                             )a where row_number=1 and url NOT IN(
        #
        #         select url  from entity_urls eu inner join
        #                             lab lb on eu.entity_id = lb.id
        #                             and eu.sitemap_identifier = 'LAB_PAGE' and eu.locality_value ilike %s and ST_DWithin(lb.location, %s, 20000)
        #                             and eu.is_valid = True
        #                             order by st_distance(lb.location, %s) asc limit 10
        #     )limit 10'''

        query = '''select a.url, a.title from
                      (
                select eu.url, lb.name title,
                row_number() over (partition by ln.id order by st_distance(eu.location, %s) ASC) as row_number 
                from entity_urls eu inner join lab lb on eu.entity_id = lb.id and eu.sitemap_identifier = 'LAB_PAGE' and 
                eu.is_valid = True  and lower(eu.locality_value) = lower(%s) and
                ST_DWithin(eu.location, %s, 20000)
                inner join seo_lab_network sln on lb.network_id = sln.lab_network_id 
                inner join lab_network ln on ln.id=sln.lab_network_id  order by rank
                                    )a where row_number=1 limit 20'''

        query_result = self.get_urls(query, [self.centroid.ewkt, self.locality, self.centroid.ewkt])

        for data in query_result:
            if not urls_nearby_labs.__contains__(data.get('url')):
                result.append({'url': data.get('url'), 'title': data.get('title')})
        return result


class LabLocalityCityFooter(Footer):
    def __init__(self, entity):
        self.locality_id = int(entity.locality_id)
        self.locality = entity.locality_value
        self.centroid = entity.locality_location
        self.sub_locality_id = int(entity.sublocality_id)
        self.sub_locality = entity.sublocality_value
        self.sublocality_location = entity.sublocality_location

    def get_footer(self):
        response = {}
        response['menu'] = []

        if self.locality_id:
            labs_in_nearby_localities = self.labs_in_nearby_localities()
            if labs_in_nearby_localities:
                response['menu'].append(
                    {'sub_heading': 'Labs in nearby localities', 'url_list': labs_in_nearby_localities})

        if self.locality_id and self.sublocality_location:
            top_labs_in_localities = self.top_labs_in_localities()
            if top_labs_in_localities:
                response['menu'].append(
                    {'sub_heading': 'Popular labs in City', 'url_list': top_labs_in_localities})

        return response

    def labs_in_nearby_localities(self):
           query = '''select eu.url, concat('Labs',' in ',eu.sublocality_value,' ',eu.locality_value) title from entity_urls eu where
               sitemap_identifier ='LAB_LOCALITY_CITY'  
               and is_valid=True
               and locality_id = %s
               order by count desc limit 10'''

           return self.get_urls(query, [self.locality_id])

    def top_labs_in_localities(self):
        result = []

        query = '''select * from
                        (                                                                       
                        select eu.url, lb.name title,
                        row_number() over (partition by ln.id order by st_distance(eu.location, %s)asc ) as row_number 
                        from entity_urls eu inner join lab lb on eu.entity_id = lb.id and eu.sitemap_identifier = 'LAB_PAGE' and 
                        ST_DWithin(eu.location, %s, 20000) and lower(eu.sublocality_value) = lower(%s)  
                        and eu.is_valid = True inner join seo_lab_network sln on lb.network_id = sln.lab_network_id
                        left join lab_network ln on ln.id=sln.lab_network_id  order by rank
                        )a where row_number=1 limit 10'''

        query_result = self.get_urls(query, [self.sublocality_location.ewkt, self.sublocality_location.ewkt, self.sub_locality])

        for data in query_result:
            result.append({'url': data.get('url'), 'title': data.get('title')})
        return result


class LabCityFooter(Footer):
    def __init__(self, entity):
        self.locality_id = int(entity.locality_id)
        self.locality = entity.locality_value
        self.centroid = entity.locality_location

    def get_footer(self):
            response = {}
            response['menu'] = []

            labs_in_top_cities = self.labs_in_top_cities()
            if labs_in_top_cities:
                response['menu'].append(
                    {'sub_heading': 'Labs in Top Cities', 'url_list': labs_in_top_cities})

            # top_specialities_in_city = self.specialist_in_city()
            # if top_specialities_in_city:
            #     response['menu'].append(
            #         {'sub_heading': 'Top specialities in %s' % self.locality, 'url_list': top_specialities_in_city})
            if self.centroid and self.locality_id:
                top_labs_in_cities = self.top_labs_in_cities()
                if top_labs_in_cities:
                    response['menu'].append(
                        {'sub_heading' : 'Top Labs in Cities', 'url_list': top_labs_in_cities})

            if response['menu']:
                response['heading'] = 'Dynamic footer on doctors in %s' % self.locality

            return response

    def labs_in_top_cities(self):
            query = '''select eu.url, concat('Labs in ', eu.locality_value) title from entity_urls eu inner join
                        seo_cities sc on lower(eu.locality_value) = lower(sc.city) 
                        and  eu.sitemap_identifier = 'LAB_CITY' and eu.is_valid = True order by rank limit 10'''

            return self.get_urls(query,[])

    def top_labs_in_cities(self):
        result = []
        query = '''select * from
                        (
                        select eu.url, lb.name title,
                        row_number() over (partition by ln.id order by st_distance(eu.location, %s)asc ) as row_number 
                        from entity_urls eu inner join lab lb on eu.entity_id = lb.id and eu.sitemap_identifier = 'LAB_PAGE' 
                        and ST_DWithin(eu.location, %s, 20000) and lower(eu.locality_value) = lower(%s)
                        and eu.is_valid = True inner join seo_lab_network sln on lb.network_id = sln.lab_network_id
                        left join lab_network ln on ln.id=sln.lab_network_id  order by rank
                        )a where row_number=1 limit 10'''

        query_result = self.get_urls(query, [self.centroid.ewkt, self.centroid.ewkt, self.locality])

        for data in query_result:
            result.append({'url': data.get('url'), 'title': data.get('title')})
        return result


class SpecialityCityFooter(Footer):
    def __init__(self, entity):
        self.specialization_id = int(entity.specialization_id)
        self.locality_id = int(entity.locality_id)
        self.specialization = entity.specialization
        self.locality = entity.locality_value
        self.location = entity.locality_location

    def get_footer(self):
        response = {}
        response['menu'] = []

        if self.specialization_id and self.locality:
            top_specialities_in_city = self.specialist_in_city()
            if top_specialities_in_city:
                response['menu'].append({'sub_heading': 'Top specialities in %s' % self.locality, 'url_list': top_specialities_in_city})

        if self.specialization_id and self.locality and self.location:
            speciality_in_popular_localities = self.specialist_in_popular_localities()
            if speciality_in_popular_localities:
                response['menu'].append(
                    {'sub_heading': '%s in Popular Localities in %s' % (self.specialization, self.locality),
                     'url_list': speciality_in_popular_localities})

        # if self.specialization_id and self.locality_id:
        #     speciality_in_top_cities = self.specialist_in_top_cities()
        #     if speciality_in_top_cities:
        #         response['menu'].append(
        #             {'sub_heading': '%s in Top Cities' % self.specialization, 'url_list': speciality_in_top_cities})

        if response['menu']:
            response['heading'] = '%s in %s Search Page' % (self.specialization, self.locality)

        return response


    def specialist_in_popular_localities(self):
        if self.location:
            query = '''select eu.url, concat(eu.specialization,'s in ',eu.sublocality_value ,', ',eu.locality_value) title from entity_urls eu where
                specialization_id = %s and sitemap_identifier ='SPECIALIZATION_LOCALITY_CITY'  
                and ST_DWithin(sublocality_location, %s, 10000) and is_valid=True 
                and lower(locality_value) = lower(%s)
                order by count desc limit 10'''
            return self.get_urls(query,[self.specialization_id, self.location.ewkt, self.locality])
        else:
            return []


    def specialist_in_city(self):

        query = ''' select eu.url, concat(eu.specialization,'s in ',eu.locality_value) title 
                    from seo_specialization ss inner join entity_urls eu on ss.specialization_id = eu.specialization_id 
                    and lower(eu.locality_value) = lower(%s) and eu.sitemap_identifier='SPECIALIZATION_CITY' 
                    and eu.is_valid=True and eu.specialization_id!=%s order by count desc limit 20'''

        return  self.get_urls(query, [self.locality, self.specialization_id])

    # def specialist_in_top_cities(self):
    #
    #     query = '''select url, concat(eu.specialization,' in ',eu.locality_value) title from seo_cities sc inner join entity_urls eu
    #                            on sc.city iLIKE eu.locality_value and eu.sitemap_identifier='SPECIALIZATION_CITY'
    #                            and specialization_id = %s and eu.locality_id !=%s and eu.is_valid=True order by rank limit 10;'''
    #     return  self.get_urls(query, [self.specialization_id, self.locality_id])


class SpecialityLocalityFooter(Footer):
    def __init__(self, entity):
        self.specialization_id = int(entity.specialization_id)
        self.locality_id = int(entity.locality_id)
        self.specialization = entity.specialization
        self.locality = entity.locality_value
        self.sublocality_id = int(entity.sublocality_id)
        self.sublocality = entity.sublocality_value
        self.sublocality_location = entity.sublocality_location
        self.centroid = entity.sublocality_location

    def get_footer(self):
        response = {}
        response['menu'] = []

        specialist_in_nearby_localities = self.specialist_in_popular_localities()
        if specialist_in_nearby_localities:
            response['menu'].append({'sub_heading': '%s in nearby localities' % self.specialization,
                                     'url_list': specialist_in_nearby_localities})

        top_specialities_in_locality = self.specialist_in_locality()
        if top_specialities_in_locality:
            response['menu'].append({'sub_heading': 'Popular Doctors in %s %s' % (self.sublocality, self.locality), 'url_list': top_specialities_in_locality})

        # speciality_in_top_cities = self.specialist_in_top_cities()
        # if speciality_in_top_cities:
        #         response['menu'].append({'sub_heading': '%s in Top Cities' % self.specialization, 'url_list': speciality_in_top_cities})


        if response['menu']:
            response['heading'] = '%s in %s Search Page' % (self.specialization, self.locality)

        return response

    def specialist_in_popular_localities(self):
        if self.centroid:
            query = '''select eu.url, concat(eu.specialization,'s in ',eu.sublocality_value, ', ',eu.locality_value ) title from entity_urls eu where
                specialization_id = %s and sitemap_identifier ='SPECIALIZATION_LOCALITY_CITY'  
                and ST_DWithin(sublocality_location, %s, 10000) and is_valid=True 
                and lower(locality_value) = lower(%s) and sublocality_id != %s
                order by count desc limit 10'''
            return self.get_urls(query, [self.specialization_id, self.centroid.ewkt, self.locality, self.sublocality_id])
        else:
            return []


    def specialist_in_locality(self):

        query = ''' select eu.url, concat(eu.specialization,'s in ', eu.sublocality_value, ', ',  eu.locality_value) title from seo_specialization ss 
                    inner join entity_urls eu on ss.specialization_id = eu.specialization_id 
                    and eu.sublocality_id=%s and eu.sitemap_identifier='SPECIALIZATION_LOCALITY_CITY' 
                    and eu.is_valid=True and eu.specialization_id!=%s order by count desc limit 10'''

        return self.get_urls(query, [self.sublocality_id, self.specialization_id])

    # def specialist_in_top_cities(self):
    #     result = []
    #
    #     query = ''' select url,max(title), min(rank) from
    #                 (select url, -1 as rank, concat(eu.specialization,' in ', eu.locality_value) title  from entity_urls eu
    #                 where sitemap_identifier='SPECIALIZATION_CITY' and is_valid=True and specialization_id = %s and locality_id = %s
    #                 union
    #                 select url, rank, concat(eu.specialization,' in ', eu.locality_value) title  from entity_urls eu
    #                 inner join seo_cities sc on eu.locality_value = sc.city
    #                 where sitemap_identifier='SPECIALIZATION_CITY' and is_valid=True and specialization_id = %s
    #                 )x group by url order by min(rank) limit 10'''
    #
    #     query_result = self.get_urls(query,[self.specialization_id, self.locality_id, self.specialization_id])
    #
    #     for data in query_result:
    #         result.append({'url': data.get('url'), 'title': data.get('max')})
    #     return result


class DoctorProfileFooter(Footer):
    def __init__(self, entity):
        #self.locality_id = int(entity.locality_id)
        #self.locality = entity.locality_value
        #self.centroid = entity.sublocality_location
        #self.sublocality_location = entity.sublocality_location
        self.sublocality_id = int(entity.sublocality_id ) if entity.sublocality_id else None
        self.locality_id = int(entity.locality_id) if entity.locality_id else None
        self.sublocality = entity.sublocality_value
        self.locality = entity.locality_value
        self.specialization_id = entity.specialization_id
        self.specialization = entity.specialization
        self.centroid = entity.location

        # location_id = int(entity.extras.get('location_id'))
        # address = EntityAddress.objects.filter(pk=location_id)
        # if address:
        #     address = address[0]
        #
        # if address:
        #     self.centroid = address.centroid
        #
        #     if address.type_blueprint=='SUBLOCALITY':
        #         self.sublocality_id = address.id
        #         self.sublocality = address.alternative_value
        #         address = EntityAddress.objects.filter(pk=address.parent).first()
        #         if address:
        #             self.locality_id = address.id
        #             self.locality= address.alternative_value
        #
        #     else:
        #         self.locality_id = address.id
        #         self.locality = address.alternative_value

    def get_footer(self):
        response = {}
        response['menu'] = []

        if self.centroid and self.specialization and self.specialization_id:
            specialist_in_nearby_localities = self.specialist_in_popular_localities()
            if specialist_in_nearby_localities:
                response['menu'].append({'sub_heading': '%s in nearby localities' % (self.specialization),
                                             'url_list': specialist_in_nearby_localities})

        if self.sublocality_id and self.sublocality and self.locality:
            top_specialities_in_locality = self.specialist_in_locality()
            if top_specialities_in_locality:
                response['menu'].append(
                    {'sub_heading': 'Popular Doctors in %s %s' %(self.sublocality, self.locality),
                     'url_list': top_specialities_in_locality})

        # if self.locality_id and self.locality:
        #     #print(str(self.locality_id))
        #     top_specialities_in_city = self.specialist_in_city()
        #     if top_specialities_in_city:
        #         response['menu'].append({'sub_heading': 'Popular Doctors in %s' % (self.locality), 'url_list': top_specialities_in_city})

        if response['menu']:
            response['heading'] = 'Dynamic Footer on Doctor Detail Page'

        return response

    def specialist_in_locality(self):

        query = ''' select eu.url, concat(eu.specialization,'s in ', eu.sublocality_value, ', ',  eu.locality_value) title from seo_specialization ss 
                       inner join entity_urls eu on ss.specialization_id = eu.specialization_id 
                       and eu.sublocality_id=%s and eu.sitemap_identifier='SPECIALIZATION_LOCALITY_CITY' 
                       and eu.is_valid=True order by count desc limit 10'''

        return self.get_urls(query, [self.sublocality_id])
    #
    # def specialist_in_city(self):
    #
    #     query = ''' select url, concat(eu.specialization,' in ',eu.locality_value) title from seo_specialization ss inner join entity_urls eu on ss.specialization_id = eu.specialization_id
    #                    and lower(eu.locality_value) = lower(%s) and eu.sitemap_identifier='SPECIALIZATION_CITY'
    #                    and eu.is_valid=True order by count desc limit 10'''
    #
    #     return self.get_urls(query, [self.locality])

    def specialist_in_popular_localities(self):
        query = '''select eu.url, concat(eu.specialization,'s in ',eu.sublocality_value,', ',eu.locality_value) title from entity_urls eu where
                specialization_id = %s and sitemap_identifier ='SPECIALIZATION_LOCALITY_CITY'  
                and ST_DWithin(sublocality_location, %s, 10000) and is_valid=True                 
                order by count desc limit 10'''
        return self.get_urls(query, [self.specialization_id, self.centroid.ewkt])


class DoctorCityFooter(Footer):

    def __init__(self, entity):
        self.locality_id = int(entity.locality_id) if entity.locality_id else None
        self.locality = entity.locality_value
        self.centroid = entity.locality_location

    def get_footer(self):
        response = {}
        response['menu'] = []

        if self.locality and self.centroid:
            doctors_in_top_localities = self.doctor_in_top_localities()
            if doctors_in_top_localities:
                response['menu'].append({'sub_heading': 'Doctors in Top Localities', 'url_list': doctors_in_top_localities})

        if self.locality:
            top_specialities_in_city = self.specialist_in_city()
            if top_specialities_in_city:
                response['menu'].append({'sub_heading': 'Top specialities in %s' % self.locality, 'url_list': top_specialities_in_city})

        if response['menu']:
            response['heading'] = 'Dynamic footer on doctors in %s' % self.locality

        return response

    def doctor_in_top_localities(self):
        query = '''select eu.url, concat('Doctors',' in ',eu.sublocality_value,', ',eu.locality_value) title from entity_urls eu where
                sitemap_identifier ='DOCTORS_LOCALITY_CITY'  
                and ST_DWithin(sublocality_location, %s,10000) and is_valid=True
                and lower(locality_value) = lower(%s)
                order by count desc limit 10'''
        return self.get_urls(query, [self.centroid.ewkt, self.locality])

    def specialist_in_city(self):

        query = ''' select eu.url, concat('Best ', eu.specialization,'s in ',eu.locality_value) title from seo_specialization ss inner join entity_urls eu on ss.specialization_id = eu.specialization_id 
                    and lower(eu.locality_value) = lower(%s) and eu.sitemap_identifier='SPECIALIZATION_CITY'  
                    and eu.is_valid=True order by count desc limit 20'''

        return  self.get_urls(query,[self.locality])


class DoctorLocalityCityFooter(Footer):
    def __init__(self, entity):
        self.sublocality_id = int(entity.sublocality_id)
        self.locality_id = int(entity.locality_id)
        self.sublocality = entity.sublocality_value
        self.locality = entity.locality_value
        # self.specialization_id = int(entity.specialization_id)
        self.specialization = entity.specialization
        self.centroid = entity.sublocality_location


    def get_footer(self):
        response = {}
        response['menu'] = []

        if self.centroid and self.locality and self.sublocality_id:
            doctors_in_nearby_popular_localities = self.doctor_in_popular_localities()
            if doctors_in_nearby_popular_localities:
                response['menu'].append({'sub_heading': 'Doctors in nearby localities',
                                             'url_list': doctors_in_nearby_popular_localities})

        if self.sublocality_id and self.sublocality and self.locality:
            popular_doctors_in_locality = self.doctors_in_locality()
            if popular_doctors_in_locality:
                response['menu'].append(
                    {'sub_heading': 'Popular Doctors in %s %s' %(self.sublocality, self.locality),
                     'url_list': popular_doctors_in_locality})

        # if self.locality_id and self.locality:
        #     print(str(self.locality_id))
        #     doctors_in_top_cities = self.doctors_in_top_city()
        #     if doctors_in_top_cities:
        #         response['menu'].append({'sub_heading': 'Doctors in top Cities', 'url_list': doctors_in_top_cities})

        if response['menu']:
            response['heading'] = 'Dynamic Footer on Doctor in %s %s' %(self.sublocality, self.locality)

        return response

    def doctors_in_locality(self):

        query = ''' select eu.url, concat('Best ', eu.specialization,'s in ', eu.sublocality_value, ', ',  eu.locality_value) title from seo_specialization ss 
                           inner join entity_urls eu on ss.specialization_id = eu.specialization_id 
                           and eu.sublocality_id=%s and eu.sitemap_identifier='SPECIALIZATION_LOCALITY_CITY' 
                           and eu.is_valid=True and eu.locality_value iLIKE %s order by count desc limit 10'''

        return self.get_urls(query, [self.sublocality_id, self.locality])

    # def doctors_in_top_city(self):
    #     result = []
    #
    #     query = ''' select url,max(title), min(rank) from
    #                 (select url, -1 as rank, concat('Doctors in ', eu.locality_value) title  from entity_urls eu
    #                 where sitemap_identifier='DOCTORS_CITY' and is_valid=True and locality_id = %s
    #                 union
    #                 select url, rank, concat('Doctors in ', eu.locality_value) title  from entity_urls eu
    #                 inner join seo_cities sc on eu.locality_value = sc.city
    #                 where sitemap_identifier='DOCTORS_CITY' and is_valid=True
    #                 )x group by url order by min(rank) limit 10'''
    #
    #     query_result = self.get_urls(query, [self.locality_id])
    #
    #     for data in query_result:
    #         result.append({'url': data.get('url'), 'title': data.get('max')})
    #     return result

    def doctor_in_popular_localities(self):
        if self.centroid:
            query = '''select eu.url, concat('Doctors in ',eu.sublocality_value, ', ',eu.locality_value ) title from entity_urls eu where
                sitemap_identifier='DOCTORS_LOCALITY_CITY'  
                and ST_DWithin(sublocality_location, %s, 10000) and is_valid=True 
                and lower(locality_value) = lower(%s) and sublocality_id != %s
                order by count desc limit 10'''
            return self.get_urls(query,[self.centroid.ewkt, self.locality, self.sublocality_id])
        else:
            return []


class DoctorsCitySearchViewSet(viewsets.GenericViewSet):

    def footer_api(self, request):
        url = request.GET.get('url')
        if not url:
            return Response(status=status.HTTP_404_NOT_FOUND)
        page = request.GET.get('page')
        if not page:
            page = 1

        url = url.lower()
        entity = location_models.EntityUrls.objects.filter(url=url, is_valid=True)
        if not len(entity)>0:
            return Response(status=status.HTTP_404_NOT_FOUND)
        response = {}
        if int(page)>5:
            return Response(response)

        entity = entity[0]
        footer = None
        title = dict()
        title_url = dict()
        city_entity = None
        spec_city_entity= None
        try:
            if entity.sitemap_identifier == EntityUrls.SitemapIdentifier.SPECIALIZATION_CITY:
                footer = SpecialityCityFooter(entity)
            elif entity.sitemap_identifier == EntityUrls.SitemapIdentifier.SPECIALIZATION_LOCALITY_CITY:
                footer = SpecialityLocalityFooter(entity)
            elif entity.sitemap_identifier == EntityUrls.SitemapIdentifier.DOCTOR_PAGE:
                footer = DoctorProfileFooter(entity)
            elif entity.sitemap_identifier == EntityUrls.SitemapIdentifier.DOCTORS_CITY:
                if page and int(page) == 1:
                    footer = DoctorCityFooter(entity)
            elif entity.sitemap_identifier == EntityUrls.SitemapIdentifier.LAB_CITY:
                footer = LabCityFooter(entity)
            elif entity.sitemap_identifier == EntityUrls.SitemapIdentifier.LAB_LOCALITY_CITY:
                footer = LabLocalityCityFooter(entity)
            elif entity.sitemap_identifier == EntityUrls.SitemapIdentifier.LAB_PAGE:
                footer = LabProfileFooter(entity)
            elif entity.sitemap_identifier == EntityUrls.SitemapIdentifier.DOCTORS_LOCALITY_CITY:
                if page and int(page) == 1:
                    footer = DoctorLocalityCityFooter(entity)

            if footer:
                response = footer.get_footer()

        except Exception as e:
            logger.error(str(e))

        if entity.sitemap_identifier == 'SPECIALIZATION_LOCALITY_CITY':
            spec_city_entity = EntityUrls.objects.filter(is_valid=True, specialization=entity.specialization,
                                                    locality_value=entity.locality_value, sitemap_identifier='SPECIALIZATION_CITY').first()

        if spec_city_entity and spec_city_entity.specialization and spec_city_entity.locality_value:
            title[1] = spec_city_entity.specialization + ' in ' + spec_city_entity.locality_value
            title[2] = 'Best ' + spec_city_entity.specialization + ' in ' + spec_city_entity.locality_value
            title[3] = 'Top ' + spec_city_entity.specialization + ' in ' + spec_city_entity.locality_value
            title[4] = spec_city_entity.specialization + ' near me'
            title[5] = 'Find ' + spec_city_entity.specialization + ' near you'
            title_url = {'title': title[int(page)], 'url': spec_city_entity.url}
            if response and response.get('menu'):
                response.get('menu').insert(0, {'sub_heading': spec_city_entity.specialization + ' in ' + spec_city_entity.locality_value, 'url_list': [title_url]})

        if entity.sitemap_identifier == 'DOCTORS_LOCALITY_CITY':
            city_entity = EntityUrls.objects.filter(is_valid=True, locality_value=entity.locality_value, sitemap_identifier='DOCTORS_CITY').first()

        if city_entity and city_entity.locality_value:
            title[1] = 'Doctors in ' + city_entity.locality_value
            title[2] = 'Best doctors in ' + city_entity.locality_value
            title[3] = 'Top doctors in ' + city_entity.locality_value
            title[4] = 'Doctors near me'
            title[5] = 'Find doctors near you'
            title_url = {'title': title[int(page)], 'url': city_entity.url}
            if response and response.get('menu'):
                response.get('menu').insert(0, {'sub_heading': 'Doctors in '+ city_entity.locality_value , 'url_list': [title_url]})

        return Response(response)


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
                # extra_info_dict = related_entity_url_obj.additional_info
                # location_id = extra_info_dict.get('location_id', None)
                # if not location_id:
                if related_entity_url_obj.sublocality_id:
                    location_id = related_entity_url_obj.sublocality_id
                elif related_entity_url_obj.locality_id:
                    location_id = related_entity_url_obj.locality_id
                else:
                    return Response(response)

                location_dict = dict()
                location_address = location_models.EntityAddress.objects.get(id=location_id)
                if location_address.type == 'SUBLOCALITY':
                    #city_location_address = location_models.EntityAddress.objects.get(id=location_address.parent)
                    city_location_address = location_address.parent
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
                                if doctor.doctorpracticespecializations.all().filter(specialization__id=related_entity_url_obj.specialization_id).exists():
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
        # cities = location_models.EntityUrls.objects.filter(sitemap_identifier='DOCTORS_CITY',count__gt=0).order_by('-count').\
        #     extra(select={'rank':'SELECT rank FROM "seo_cities" WHERE "entity_urls".locality_value ilike "seo_cities".city'}).\
        #     extra(order_by=['rank']).values_list('locality_value', flat=True).distinct()

        query = '''select max(eu.url), eu.locality_value, count(*) from entity_urls eu 
                    left join seo_cities sc on eu.locality_value = sc.city
                    inner join entity_urls eurl on eu.locality_value = eurl.locality_value and eurl.url_type='SEARCHURL'
                     and eurl.sitemap_identifier = 'SPECIALIZATION_CITY' 
                     where eu.sitemap_identifier='DOCTORS_CITY' and eu.is_valid =True
                     group by eu.locality_value order by max(sc.rank) asc nulls last,count(*) desc 
                     '''

        sql_urls = RawSql(query, []).fetch_all()

        result =[]

        for data in sql_urls:
             result.append(data.get('locality_value'))

        return Response({"cities": result})

    def list_urls_by_city(self, request, city):
        if not city:
            return Response(status=status.HTTP_404_NOT_FOUND)

        entity = location_models.EntityUrls.objects.filter(locality_value__iexact=city, url_type='SEARCHURL',
                                                           entity_type__iexact='Doctor', is_valid=True,
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
        query = '''select specialization_id,max(specialization) specialization  from entity_urls where 
                 sitemap_identifier='SPECIALIZATION_LOCALITY_CITY' group by specialization_id order by count(*) desc'''
        # query = '''select eu.specialization_id, max(eu.specialization) specialization from entity_urls eu 
        #         inner join entity_urls eur on eu.specialization_id = eur.specialization_id
        #         where eu.sitemap_identifier = 'SPECIALIZATION_CITY'
        #         and eur.sitemap_identifier = 'SPECIALIZATION_LOCALITY_CITY'
        #         group by eu.specialization_id order by count(*) desc'''

        result = RawSql(query,[]).fetch_all()


        # specializations = location_models.EntityUrls.objects.filter(url_type='SEARCHURL', entity_type__iexact='Doctor',
        #                                                             sitemap_identifier='SPECIALIZATION_CITY',
        #                                                             specialization_id__gt=0,
        #                                                             specialization__isnull=False).values(
        #                                                              'specialization', 'specialization_id').distinct()

        return Response({"specialization_inventory": result})

    def specialities_in_localities_list(self, request, specialization_id):
        if not specialization_id:
            return Response(status=status.HTTP_404_NOT_FOUND)

        pages = None
        query = '''select * from (select z.*, dense_rank() over( order by z.sub_count desc,z.locality) city_num from
                (
                    select * from (select x.*, row_number() over(partition by locality order by count desc) row_num,
                                 count(*) over (partition by locality) sub_count
                                 from
                                (select locality_value, sublocality_value, specialization, specialization_id,url,count,extras,
                                 locality_value as locality
                                 from entity_urls where is_valid=True
                                and sitemap_identifier = 'SPECIALIZATION_LOCALITY_CITY' and specialization_id = %s
                                )x)y where row_num<=20 order by sub_count desc)z
                )t ''' 

        query1 ='''{query} order by city_num, row_num'''.format(query=query)

        sql_urls = RawSql(query1,[specialization_id]).fetch_all()
        if sql_urls:
            pages = int(sql_urls[-1].get('city_num')/25)
            if not sql_urls[-1].get('city_num') % 25 == 0:
                pages = pages+1

            page_no = request.GET.get('page_no', None)
            if not page_no:
                page_no = 1
            page_no = int(page_no)
            start = (page_no-1) * 25 + 1
            end = page_no * 25

            seo_query_result = '''{query}  where city_num between %s and %s  order by city_num, row_num'''.format(query=query)

            seo_result = RawSql(seo_query_result, [specialization_id, start, end]).fetch_all()
            paginated_specialists = []
            result = []

            for data in seo_result:
                city_title = None
                if data.get('row_num') ==1:
                    result = {'speciality_url_title': []}
                    city_title = data.get('locality_value')
                    if city_title:
                        # paginated_specialists.append({"city_title": city_title})
                        result['city_title'] = city_title
                        speciality_url = []
                    paginated_specialists.append(result)
                title = data.get('specialization') + " in " + data.get('sublocality_value') + " " + data.get('locality_value')
                result['speciality_url_title'].append({"title": title, "url": data.get('url')})

            return Response({'pages': pages, 'paginated_specialists': paginated_specialists, "page_no": page_no})

        else:
            return Response(status=status.HTTP_404_NOT_FOUND)

    def static_footer(self, request):
        static_footer_urls = []
        cities = self.top_cities(EntityUrls.SitemapIdentifier.DOCTORS_CITY)
        # doctor_footer_urls = []
        doctor_urls_list = []
        for city in cities:
            if EntityUrls.objects.filter(sitemap_identifier='DOCTORS_CITY', url_type='SEARCHURL',
                                                                      is_valid=True).exists():

                if EntityUrls.objects.filter(sitemap_identifier='DOCTORS_CITY',locality_value=city,
                                                                      is_valid=True).values('url'):

                    doctor_url = EntityUrls.objects.filter(sitemap_identifier='DOCTORS_CITY',
                                                                      locality_value=city,
                                                                      is_valid=True)
                    if doctor_url.exists():
                        doctor_urls_list.append({'title': 'Doctors in %s' % city, 'url': doctor_url.first().url})
            else:
                doctor_urls_list.append({})

        static_footer_urls.append({'title': 'Doctors in Top Cities', 'result': doctor_urls_list})

        lab_urls_list = []
        cities = self.top_cities(EntityUrls.SitemapIdentifier.LAB_CITY)
        for city in cities:
            if EntityUrls.objects.filter(sitemap_identifier='LAB_CITY', url_type='SEARCHURL',
                                                                   is_valid=True).exists():
                if EntityUrls.objects.filter(sitemap_identifier='LAB_CITY', locality_value=city,
                                          is_valid=True).values('url'):

                    lab_url =EntityUrls.objects.filter(sitemap_identifier='LAB_CITY', locality_value=city,
                                                                   is_valid=True)
                    if lab_url.exists():
                        lab_urls_list.append({'title': 'Labs in %s' % city,  'url': lab_url.first().url})
            else:
                lab_urls_list.append({})
        static_footer_urls.append({'title': 'Labs in Top Cities', 'result': lab_urls_list})

        return Response({"static_footer": static_footer_urls})

    def top_cities(self, sitemap_identifier):
        query = '''select city from seo_cities sc inner join entity_urls eu
                   on sc.city iLIKE eu.locality_value and eu.sitemap_identifier=%s 
                   and eu.is_valid=True order by rank limit 10;'''

        sql_urls = RawSql(query, [sitemap_identifier]).fetch_all()

        result = []

        for data in sql_urls:
            result.append(data.get('city'))

        return result

    def top_specialities_in_top_cities(self,request):
        cities = self.top_cities(EntityUrls.SitemapIdentifier.DOCTORS_CITY)
        list = []
        resp = {}

        query = ''' select city, eu.url, concat(eu.specialization,' in ', city) title from 
                    (
                    (select city , rank as city_rank from seo_cities order by rank limit 10) sc
                    inner join 
                    (select specialization_id,rank as specialization_rank from seo_specialization order by rank nulls last limit 5) ss on true
                    )x 
                    inner join 
                    entity_urls eu on eu.is_valid=true and eu.sitemap_identifier='SPECIALIZATION_CITY' and lower(x.city) = lower(eu.locality_value) 
                    and eu.specialization_id=x.specialization_id order by city_rank nulls last ,city, specialization_rank nulls last, x.specialization_id'''
        result = RawSql(query, []).fetch_all()
        for data in result:
            if not resp.get(data.get('city')):
                title = 'Doctors in ' + data.get('city')
                resp[data.get('city')] = {'title': title, 'urls': []}
            resp[data.get('city')]['urls'].append({'url': data.get('url'),'title': data.get('title')})

        return Response(resp.values())
