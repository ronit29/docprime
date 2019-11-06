from django.db.models import Prefetch, Case, When, F
from collections import OrderedDict
from django.template.defaultfilters import slugify
from django.contrib.gis.geos import Point
from django.db.models import Count, Max

from ondoc.api.v1.utils import RawSql
from ondoc.doctor.models import Doctor, DoctorPracticeSpecialization, Hospital, PracticeSpecialization
from ondoc.location.models import EntityUrls, TempURL
from ondoc.location.services.doctor_urls import PageUrlCache


class HospitalURL():

    def __init__(self):
        query = '''select nextval('entity_url_version_seq') as inc;'''
        seq = RawSql(query, []).fetch_all()
        self.sequence = seq[0]['inc']
        RawSql('truncate table temp_url', []).execute()

        ea_limit = RawSql('select min(id) min, max(id) max from entity_address', []).fetch_all()

        self.min_ea = ea_limit[0]['min']
        self.max_ea = ea_limit[0]['max']
        self.step = 2000

    def create(self):
        # self.create_hosp_search_urls()
        self.create_hosp_search_urls_new()
        # self.create_hospital_page_urls()
        self.create_hosp_page_urls_with_hosp_details()
        # self.update_breadcrumbs()
        self.insert_search_urls()
        self.update_breadcrumbs_without_dist()

    def create_hosp_search_urls_new(self):
        hosp_search_query = ''' select hospital_id, sublocality_value,
                                locality_value, count,  entity_type, url_type, is_valid, bookable_doctors_count from (
                                select  ROW_NUMBER() OVER (PARTITION BY hospital_id) AS row_num, hospital_id, sublocality_value,
                                locality_value, count,  entity_type, url_type, is_valid,
                                json_build_object('bookable_doctors_count',bookable_doctors_count,'bookable_doctors_2km',bookable_doctors_2km)
                                as bookable_doctors_count
                                from (
                                select max(h.id) as hospital_id, max(h.locality) as sublocality_value, max(h.city) as locality_value, count(distinct d.id) count,
                                COUNT(DISTINCT CASE WHEN d.enabled_for_online_booking=True and dc.enabled_for_online_booking=True
                                and h.enabled_for_online_booking=True then d.id else null END) as bookable_doctors_count,
                                COUNT(DISTINCT CASE WHEN d.enabled_for_online_booking=True and dc.enabled_for_online_booking=True
                                and h.enabled_for_online_booking=True 
                                and ST_DWithin(ea.centroid::geography,h.location::geography,2000)then d.id else null end) as bookable_doctors_2km,
                                'Hospital' as entity_type, 'SEARCHURL' url_type, True as is_valid
                                from entity_address ea inner join hospital h on ((ea.type = 'LOCALITY' and lower(h.city)=lower(ea.alternative_value) and 
                                ST_DWithin(ea.centroid::geography,h.location::geography,h.search_url_locality_radius)) OR 
                                (ea.type = 'SUBLOCALITY' and lower(h.locality)=lower(ea.alternative_value) and 
                                ST_DWithin(ea.centroid::geography,h.location::geography,h.search_url_sublocality_radius))) and h.is_live=true
                                and ea.type IN ('SUBLOCALITY' , 'LOCALITY') and ea.use_in_url=true
                                inner join doctor_clinic dc on dc.hospital_id = h.id 
                                and dc.enabled=true inner join doctor d on dc.doctor_id= d.id and d.is_live=true
                                where ea.id>=%d and ea.id<%d
                                group by ea.id)a )b  where row_num=1'''

        start = self.min_ea
        to_create = []
        while start < self.max_ea:
            query = hosp_search_query % (start, start + self.step)
            hosp_data = RawSql(query, []).fetch_all()
            if hosp_data:
                hospital_ids = (data.get('hospital_id') for data in hosp_data)
                hosp_loc_obj = Hospital.objects.filter(id__in=hospital_ids).values('id','location')
                hosp_loc_dict = dict()
                for data in hosp_loc_obj:
                    if not hosp_loc_dict.get(data.get('id')):
                        hosp_loc_dict[data.get('id')] = data.get('location')

                for data in hosp_data:
                    location = hosp_loc_dict[data.get('hospital_id')] if hosp_loc_dict.get(data.get('hospital_id')) else None
                    if location:
                        url_data = {}
                        url_data['is_valid'] = data.get('is_valid')
                        url_data['url_type'] = data.get('url_type')
                        url_data['entity_type'] = data.get('entity_type')
                        url_data['count'] = data.get('count')
                        url_data['bookable_doctors_count'] = data.get('bookable_doctors_count')
                        url_data['sitemap_identifier'] = 'HOSPITALS_CITY'
                        url_data['locality_latitude'] = location.y
                        url_data['locality_longitude'] = location.x
                        url_data['location'] = location
                        url_data['locality_location'] = location
                        url_data['locality_value'] = data.get('locality_value')
                        url_data['url'] = slugify('hospitals-in-' + data.get('locality_value') + '-hspcit')
                        to_create.append(TempURL(**url_data))
                        url_data['sitemap_identifier'] = 'HOSPITALS_LOCALITY_CITY'
                        url_data['sublocality_value'] = data.get('sublocality_value')
                        url_data['sublocality_latitude'] = location.y
                        url_data['sublocality_longitude'] = location.x
                        url_data['sublocality_location'] = location
                        url_data['url'] = slugify('hospitals-in-' + data.get('sublocality_value') + '-' + data.get('locality_value') + '-hsplitcit')
                        to_create.append(TempURL(**url_data))

            start = start + self.step
        TempURL.objects.bulk_create(to_create)

        update_extras_query = '''update  temp_url 
                                      set extras = case when sitemap_identifier='HOSPITALS_CITY' then
                                      json_build_object('location_json',json_build_object('locality_id',locality_id,'locality_value',locality_value, 
                                      'locality_latitude',locality_latitude,'locality_longitude',locality_longitude))

                                      else json_build_object('location_json',
                                      json_build_object('sublocality_id', sublocality_id,'sublocality_value', sublocality_value,
                                      'locality_id', locality_id, 'locality_value', locality_value,'breadcrum_url',slugify_url('hospitals-in-' || locality_value ||'-hspcit'),
                                      'sublocality_latitude',sublocality_latitude, 'sublocality_longitude',sublocality_longitude, 'locality_latitude',locality_latitude,
                                      'locality_longitude',locality_longitude))  end
                                       '''
        update_extras = RawSql(update_extras_query, []).execute()

        # clean up duplicate urls
        RawSql('''delete from temp_url where id in (select id from 
                        (select eu.*, row_number() over(partition by url ) rownum from temp_url eu  
                        )x where rownum>1
                        ) ''', []).execute()
        return 'success'

    def create_hosp_page_urls_with_hosp_details(self):

        sequence = self.sequence

        cache = PageUrlCache(EntityUrls.SitemapIdentifier.HOSPITAL_PAGE)

        to_create = []

        hosp_obj = Hospital.objects.filter(is_live=True).prefetch_related(Prefetch('assoc_doctors',
                                                                               queryset=Doctor.objects.filter(
                                                                                       is_live=True,
                                                                                       is_test_doctor=False)
                                                                                   )).order_by('hospital_type', 'id')

        hosp_obj = hosp_obj.annotate(doctors_count=Count('assoc_doctors'), bookable_doctors_count=Count(Case(
            When(assoc_doctors__enabled_for_online_booking=True, enabled_for_online_booking=True,
                 hospital_doctors__enabled_for_online_booking=True,
                 then=F('assoc_doctors__id')))))

        for hospital in hosp_obj:

            locality_value = None
            locality_latitude = None
            locality_longitude = None
            sublocality_value = None
            sublocality_longitude = None
            sublocality_latitude = None
            sequence = sequence

            print('mapped entities for hospital' + str(hospital.id))
            sublocality_value = hospital.locality
            sublocality_longitude = hospital.location.x if hospital.location else None
            sublocality_latitude = hospital.location.y if hospital.location else None
            locality_value = hospital.city
            locality_longitude = hospital.location.x if hospital.location else None
            locality_latitude = hospital.location.y if hospital.location else None

            url = "%s" % (hospital.name)

            if sublocality_value and locality_value:
                url = url + "-in-%s-%s" % (sublocality_value, locality_value)

            elif locality_value:
                url = url + "-in-%s" % (locality_value)

            else:
                url = url

            url = slugify(url)
            data = {}
            data['is_valid'] = True
            data['url_type'] = EntityUrls.UrlType.PAGEURL
            data['entity_type'] = 'Hospital'
            data['entity_id'] = hospital.id
            data['sitemap_identifier'] = EntityUrls.SitemapIdentifier.HOSPITAL_PAGE
            data['locality_value'] = locality_value
            data['locality_latitude'] = locality_latitude
            data['locality_longitude'] = locality_longitude

            if locality_latitude and locality_longitude:
                data['locality_location'] = Point(locality_longitude, locality_latitude)

            if sublocality_latitude and sublocality_longitude:
                data['sublocality_location'] = Point(sublocality_longitude, sublocality_latitude)

            data['sublocality_value'] = sublocality_value
            data['sublocality_latitude'] = sublocality_latitude
            data['sublocality_longitude'] = sublocality_longitude

            if hospital.location:
                data['location'] = hospital.location

            extras = {}
            extras['related_entity_id'] = hospital.id
            # if sublocality_id or locality_id:
            extras['location_id'] = None
            extras['locality_value'] = locality_value if locality_value else ''
            extras['sublocality_value'] = sublocality_value if sublocality_value else ''
            extras['breadcrums'] = []
            data['extras'] = extras
            data['count'] = hospital.doctors_count if hospital.doctors_count else 0
            data['bookable_doctors_count'] = {"bookable_doctors_2km": None,
                                              "bookable_doctors_count": hospital.bookable_doctors_count if hospital.bookable_doctors_count else 0}

            new_url = url

            is_duplicate = cache.is_duplicate(new_url + '-hpp', hospital.id)

            if is_duplicate:
                new_url = new_url + '-' + str(hospital.id)

            new_url = new_url + '-hpp'
            data['url'] = new_url
            new_entity = TempURL(**data)

            cache.add(new_entity)

            to_create.append(new_entity)

        TempURL.objects.bulk_create(to_create)

        return ("success")


    def insert_search_urls(self):

        seq = self.sequence

        insert_page_urls_query = '''insert into entity_urls(sequence,extras, sitemap_identifier, url, count, entity_type, 
                 url_type,  created_at, 
                 updated_at,  sublocality_latitude, sublocality_longitude, locality_latitude, 
                 locality_longitude, locality_id, sublocality_id,
                 locality_value, sublocality_value, is_valid, locality_location, sublocality_location, location, entity_id, 
                 specialization_id, specialization, breadcrumb, bookable_doctors_count)

                 select %d as sequence ,a.extras, a.sitemap_identifier,getslug(a.url) as url, a.count, a.entity_type,
                  a.url_type, now() as created_at, now() as updated_at,
                  a.sublocality_latitude, a.sublocality_longitude, a.locality_latitude, a.locality_longitude,
                  a.locality_id, a.sublocality_id, a.locality_value, a.sublocality_value, a.is_valid, 
                  a.locality_location, a.sublocality_location, a.location, entity_id, 
                  specialization_id, specialization, breadcrumb, bookable_doctors_count from temp_url a
                  where sitemap_identifier='HOSPITAL_PAGE' and (a.entity_id not in (57640, 40669, 4918, 19239, 57604, 3429, 3751, 3063, 56822, 3496, 3513, 3898, 55231,
                   56841, 56840, 4160, 30525, 24401, 2142, 3465, 38362, 2337, 56620, 56621, 27536, 31211, 56618, 33188, 56835,
                    56827, 56829, 31369, 56832, 56826, 33327, 3627, 3191, 5999, 56848, 6170, 5423, 14713, 3293, 56849, 56850, 
                    56851, 56853, 6586, 57641, 19303, 23181, 8584, 1297, 57596, 22430, 18489, 55377, 32282, 57610, 56856, 
                    56859, 56860, 3240, 52779, 2348, 2703, 227, 3068, 5347, 3380, 1980, 3560, 56071, 2861, 57639 )) ''' %seq
                    # where ((a.sitemap_identifier='HOSPITAL_PAGE'  and a.entity_id not in (select entity_id from entity_urls where
                   # sitemap_identifier='HOSPITAL_PAGE' and is_valid=True)) OR (a.sitemap_identifier!='HOSPITAL_PAGE' ))
                   # ''' %seq

        insert_search_urls_query = '''insert into entity_urls(sequence,extras, sitemap_identifier, url, count, entity_type, 
                 url_type,  created_at, 
                 updated_at,  sublocality_latitude, sublocality_longitude, locality_latitude, 
                 locality_longitude, locality_id, sublocality_id,
                 locality_value, sublocality_value, is_valid, locality_location, sublocality_location, location, entity_id, 
                 specialization_id, specialization, breadcrumb, bookable_doctors_count)

                 select %d as sequence ,a.extras, a.sitemap_identifier,getslug(a.url) as url, a.count, a.entity_type,
                  a.url_type, now() as created_at, now() as updated_at,
                  a.sublocality_latitude, a.sublocality_longitude, a.locality_latitude, a.locality_longitude,
                  a.locality_id, a.sublocality_id, a.locality_value, a.sublocality_value, a.is_valid, 
                  a.locality_location, a.sublocality_location, a.location, entity_id, 
                  specialization_id, specialization, breadcrumb, bookable_doctors_count from temp_url a
                  where sitemap_identifier in ('HOSPITALS_LOCALITY_CITY', 'HOSPITALS_CITY')  ''' % seq

        # update_seq_query = '''update entity_urls set sequence = %d where sitemap_identifier = 'HOSPITAL_PAGE' and
        #  is_valid = True''' % seq

        update_query = '''update entity_urls set is_valid=false where sitemap_identifier 
                           in ('HOSPITALS_LOCALITY_CITY', 'HOSPITALS_CITY', 'HOSPITAL_PAGE') and sequence< %d
                           and entity_id not in (57640, 40669, 4918, 19239, 57604, 3429, 3751, 3063, 56822, 3496, 3513, 3898, 55231,
                            56841, 56840, 4160, 30525, 24401, 2142, 3465, 38362, 2337, 56620, 56621, 27536, 31211, 56618, 33188, 56835,
                            56827, 56829, 31369, 56832, 56826, 33327, 3627, 3191, 5999, 56848, 6170, 5423, 14713, 3293, 56849, 56850,
                            56851, 56853, 6586, 57641, 19303, 23181, 8584, 1297, 57596, 22430, 18489, 55377, 32282, 57610, 56856,
                            56859, 56860, 3240, 52779, 2348, 2703, 227, 3068, 5347, 3380, 1980, 3560, 56071, 2861, 57639) ''' % seq

        cleanup = '''delete from entity_urls where id in (select id from 
                (select eu.*, row_number() over(partition by url order by is_valid desc, sequence desc) rownum from entity_urls eu  
                )x where rownum>1
                ) '''

        update_duplicate_entities = ''' update entity_urls set is_valid=false where id in ( select id from 
                    (select eu.*, row_number() over(partition by entity_id order by is_valid desc, sequence desc )
                     rownum from entity_urls eu  where sitemap_identifier='HOSPITAL_PAGE')x
                      where  sitemap_identifier='HOSPITAL_PAGE' and rownum >1) '''

        # for urls which we are not creating over here
        update_locality_value = ''' update entity_urls set locality_value=(select city from hospital h
		            where h.id=entity_urls.entity_id 
                    and entity_urls.sitemap_identifier='HOSPITAL_PAGE'
			        and entity_urls.is_valid=True) where sitemap_identifier='HOSPITAL_PAGE' and entity_id in (57640, 40669, 4918, 19239, 57604, 3429, 3751, 3063, 56822, 3496, 3513, 3898, 55231,
                    56841, 56840, 4160, 30525, 24401, 2142, 3465, 38362, 2337, 56620, 56621, 27536, 31211, 56618, 33188, 56835,
                    56827, 56829, 31369, 56832, 56826, 33327, 3627, 3191, 5999, 56848, 6170, 5423, 14713, 3293, 56849, 56850,
                    56851, 56853, 6586, 57641, 19303, 23181, 8584, 1297, 57596, 22430, 18489, 55377, 32282, 57610, 56856,
                    56859, 56860, 3240, 52779, 2348, 2703, 227, 3068, 5347, 3380, 1980, 3560, 56071, 2861, 57639) '''

        update_sublocality_value = ''' update entity_urls set sublocality_value=(select locality from hospital h
		            where h.id=entity_urls.entity_id 
                    and entity_urls.sitemap_identifier='HOSPITAL_PAGE'
			        and entity_urls.is_valid=True) where sitemap_identifier='HOSPITAL_PAGE' and entity_id in (57640, 40669, 4918, 19239, 57604, 3429, 3751, 3063, 56822, 3496, 3513, 3898, 55231,
                    56841, 56840, 4160, 30525, 24401, 2142, 3465, 38362, 2337, 56620, 56621, 27536, 31211, 56618, 33188, 56835,
                    56827, 56829, 31369, 56832, 56826, 33327, 3627, 3191, 5999, 56848, 6170, 5423, 14713, 3293, 56849, 56850,
                    56851, 56853, 6586, 57641, 19303, 23181, 8584, 1297, 57596, 22430, 18489, 55377, 32282, 57610, 56856,
                    56859, 56860, 3240, 52779, 2348, 2703, 227, 3068, 5347, 3380, 1980, 3560, 56071, 2861, 57639) '''

        RawSql(insert_page_urls_query, []).execute()
        RawSql(insert_search_urls_query, []).execute()
        # RawSql(update_seq_query, []).execute()
        RawSql(update_query, []).execute()
        RawSql(cleanup, []).execute()
        RawSql(update_duplicate_entities, []).execute()
        RawSql(update_locality_value, []).execute()
        RawSql(update_sublocality_value, []).execute()

        return True

    def create_hosp_search_urls(self):

        q1 = '''insert into temp_url (search_slug, count, sublocality_id, locality_id, 
                      sitemap_identifier, entity_type, url_type, is_valid, created_at, updated_at, bookable_doctors_count )
                      
                    select search_slug, count, sublocality_id,locality_id,sitemap_identifier,
                    entity_type, url_type, is_valid, now(), now(),
                    json_build_object('bookable_doctors_count',bookable_doctors_count,'bookable_doctors_2km',bookable_doctors_2km)
                    as bookable_doctors_count
                    from (
                      
                    select search_slug, count(distinct d.id) count,
                    COUNT(DISTINCT CASE WHEN d.enabled_for_online_booking=True and dc.enabled_for_online_booking=True
                    and h.enabled_for_online_booking=True then d.id else null END) as bookable_doctors_count,
                    COUNT(DISTINCT CASE WHEN d.enabled_for_online_booking=True and dc.enabled_for_online_booking=True
                    and h.enabled_for_online_booking=True 
                    and ST_DWithin(ea.centroid::geography,h.location::geography,2000)then d.id else null end) as bookable_doctors_2km,
                    case when ea.type = 'SUBLOCALITY' then ea.id end as sublocality_id,
                    case when ea.type = 'LOCALITY' then ea.id end as locality_id,
                    case when ea.type = 'LOCALITY' then 'HOSPITALS_CITY' else 'HOSPITALS_LOCALITY_CITY' end as sitemap_identifier,
                    'Hospital' as entity_type, 'SEARCHURL' url_type, True as is_valid, now(), now()
                    from entity_address ea inner join hospital h on ((ea.type = 'LOCALITY' and 
                    ST_DWithin(ea.centroid::geography,h.location::geography,15000)) OR 
                    (ea.type = 'SUBLOCALITY' and ST_DWithin(ea.centroid::geography,h.location::geography,5000))) and h.is_live=true
                    and ea.type IN ('SUBLOCALITY' , 'LOCALITY') and ea.use_in_url=true
                    inner join doctor_clinic dc on dc.hospital_id = h.id
                    and dc.enabled=true inner join doctor d on dc.doctor_id= d.id and d.is_live=true
                    where ea.id>=%d and ea.id<%d
                    group by ea.id)a '''

        start = self.min_ea
        while start < self.max_ea:
            query = q1 % (start, start + self.step)
            RawSql(query, []).execute()
            start = start + self.step

        RawSql('''update temp_url tu set locality_id = (select parent_id from entity_address where id = tu.sublocality_id)
                where locality_id is null and sublocality_id is not null''', []).execute()

        RawSql('''delete from temp_url where locality_id is null''', []).execute()

        RawSql(
            '''delete from temp_url where locality_id in (select id from entity_address where use_in_url is false)''',
            []).execute()

        RawSql(
            '''delete from temp_url where sublocality_id in (select id from entity_address where use_in_url is false)''',
            []).execute()

        RawSql('''UPDATE temp_url 
                SET locality_latitude = st_y(centroid::geometry), locality_longitude = st_x(centroid::geometry),
                locality_value = ea.alternative_value, locality_location = centroid
                FROM entity_address ea
                WHERE locality_id = ea.id ''', []).execute()

        RawSql('''UPDATE temp_url 
                SET sublocality_latitude = st_y(centroid::geometry), sublocality_longitude = st_x(centroid::geometry),
                sublocality_value = ea.alternative_value, sublocality_location = centroid
                FROM entity_address ea
                WHERE sublocality_id = ea.id 
                ''', []).execute()

        RawSql('''update temp_url set location = sublocality_location where sublocality_location is not null''',
               []).execute()

        RawSql('''update temp_url set location = locality_location where location is null''', []).execute()

        update_urls_query = '''update temp_url set url = case when sitemap_identifier = 'HOSPITALS_LOCALITY_CITY' then 
                    slugify_url(concat('hospitals-in-', search_slug, '-hsplitcit'))
                    else slugify_url(concat('hospitals-in-', search_slug, '-hspcit'))
                    end '''
        update_urls = RawSql(update_urls_query, []).execute()

        update_extras_query = '''update  temp_url 
                               set extras = case when sitemap_identifier='HOSPITALS_CITY' then
                               json_build_object('location_json',json_build_object('locality_id',locality_id,'locality_value',locality_value, 
                               'locality_latitude',locality_latitude,'locality_longitude',locality_longitude))

                               else json_build_object('location_json',
                               json_build_object('sublocality_id', sublocality_id,'sublocality_value', sublocality_value,
                               'locality_id', locality_id, 'locality_value', locality_value,'breadcrum_url',slugify_url('hospitals-in-' || locality_value ||'-hspcit'),
                               'sublocality_latitude',sublocality_latitude, 'sublocality_longitude',sublocality_longitude, 'locality_latitude',locality_latitude,
                               'locality_longitude',locality_longitude))  end
                                '''
        update_extras = RawSql(update_extras_query, []).execute()

        # clean up duplicate urls
        RawSql('''delete from temp_url where id in (select id from (select tu.*,
                row_number() over(partition by tu.url order by ea.child_count desc nulls last, tu.count desc nulls last) rownum
                from temp_url tu inner join entity_address ea on 
                case when tu.sublocality_id is not null then tu.sublocality_id else tu.locality_id end = ea.id 
                )x where rownum>1)
                ''', []).execute()

        return 'success'

    def update_breadcrumbs(self):

        # set breadcrumbs to default empty array
        RawSql('''update temp_url tu set breadcrumb=json_build_array()''', []).execute()

        RawSql('''update temp_url tu set breadcrumb=(select json_build_array(json_build_object('title', concat(locality_value, ' Hospitals ') , 'url', url, 'link_title', concat(locality_value, ' Hospitals'))) 
                   from temp_url where sitemap_identifier ='HOSPITALS_CITY' and lower(locality_value)=lower(tu.locality_value)
                   and st_dwithin(location::geography, tu.location::geography, 20000) order by st_distance(location, tu.location) asc limit 1)
                   where sitemap_identifier ='HOSPITALS_LOCALITY_CITY' ''', []).execute()

        # update for hospital profile from city if null
        RawSql('''update temp_url tu set breadcrumb = (select  breadcrumb || 
            jsonb_build_array(jsonb_build_object('title', concat(sublocality_value), 'url', url, 
            'link_title', concat('Hospitals in ', sublocality_value ,', ', locality_value) ))
            from temp_url  where sitemap_identifier ='HOSPITALS_LOCALITY_CITY' and lower(locality_value)=lower(tu.locality_value)
            and lower(sublocality_value)=lower(tu.sublocality_value) 
            and st_dwithin(location::geography, tu.location::geography, 10000) order by st_distance(location, tu.location) asc limit 1) 
            where sitemap_identifier ='HOSPITAL_PAGE'   ''', []).execute()

        RawSql('''update temp_url tu set breadcrumb=json_build_array() where breadcrumb is null ''', []).execute()

    def update_breadcrumbs_without_dist(self):
        # set breadcrumbs to default empty array
        RawSql('''update entity_urls eu set breadcrumb=json_build_array() where entity_type='Hospital' and is_valid = True
                    and sitemap_identifier in ('HOSPITALS_LOCALITY_CITY', 'HOSPITALS_CITY' , 'HOSPITAL_PAGE') ''', []).execute()

        RawSql('''update entity_urls tu set breadcrumb=(select json_build_array(json_build_object('title', concat(locality_value, ' Hospitals ') , 'url', url, 'link_title', concat(locality_value, ' Hospitals'))) 
                 from entity_urls where sitemap_identifier ='HOSPITALS_CITY' and is_valid=True and  lower(locality_value)=lower(tu.locality_value)
                 limit 1) where sitemap_identifier ='HOSPITALS_LOCALITY_CITY' and is_valid=True ''', []).execute()

        # update for hospital profile from city if null
        RawSql('''update entity_urls tu set breadcrumb = (select  breadcrumb || 
                    jsonb_build_array(jsonb_build_object('title', concat(sublocality_value), 'url', url, 
                    'link_title', concat('Hospitals in ', sublocality_value ,', ', locality_value) ))
                    from entity_urls  where sitemap_identifier ='HOSPITALS_LOCALITY_CITY' and is_valid=True and lower(locality_value)=lower(tu.locality_value)
                    and lower(sublocality_value)=lower(tu.sublocality_value) 
                     order by st_distance(location, tu.location) asc limit 1) 
                    where sitemap_identifier ='HOSPITAL_PAGE' and is_valid=True  ''', []).execute()

        RawSql('''update entity_urls tu set breadcrumb = (select  jsonb_build_array(jsonb_build_object('title', concat(locality_value, ' Hospitals '), 'url', url, 
                     'link_title', concat(locality_value, ' Hospitals') ))
                    from entity_urls  where sitemap_identifier ='HOSPITALS_CITY' and is_valid=True and lower(locality_value)=lower(tu.locality_value)
                     order by st_distance(location, tu.location) asc limit 1) 
                    where sitemap_identifier ='HOSPITAL_PAGE' and is_valid=True and breadcrumb is null  ''', []).execute()

        RawSql('''update entity_urls tu set breadcrumb=json_build_array() where breadcrumb is null  and is_valid=True and entity_type='Hospital' ''', []).execute()

    def create_hospital_page_urls(self):

        sequence = self.sequence

        cache = PageUrlCache(EntityUrls.SitemapIdentifier.HOSPITAL_PAGE)

        to_create = []

        hosp_obj = Hospital.objects.filter(is_live=True).prefetch_related('entity', 'entity__location',
                                                                          'entity__location__parent',
                                                                          Prefetch('assoc_doctors',
                                                                                   queryset=Doctor.objects.filter(
                                                                                       is_live=True, is_test_doctor=False)
                                                                                   )).order_by('hospital_type', 'id')

        hosp_obj = hosp_obj.annotate(doctors_count=Count('assoc_doctors'), bookable_doctors_count=Count(Case(
            When(assoc_doctors__enabled_for_online_booking=True, enabled_for_online_booking=True,
                 hospital_doctors__enabled_for_online_booking=True,
                 then=F('assoc_doctors__id')))))

        for hospital in hosp_obj:

            locality_value = None
            locality_id = None
            locality_latitude = None
            locality_longitude = None
            sublocality_value = None
            sublocality_id = None
            sublocality_longitude = None
            sublocality_latitude = None
            sequence = sequence
            hosp_sublocality = None
            hosp_locality = None

            entity_location_relation = hospital.entity.all()
            print('mapped entities for hospital' + str(hospital.id) + '=' + str(len(entity_location_relation)))
            for obj in entity_location_relation:

                if not hosp_sublocality and obj.location.use_in_url:
                    if obj.location.type == 'SUBLOCALITY':
                        hosp_sublocality = obj.location

            if hosp_sublocality:
                sublocality_value = hosp_sublocality.alternative_value
                sublocality_id = hosp_sublocality.id
                if hosp_sublocality.centroid:
                    sublocality_longitude = hosp_sublocality.centroid.x
                    sublocality_latitude = hosp_sublocality.centroid.y

                hosp_locality = hosp_sublocality.parent
                if hosp_locality:
                    locality_value = hosp_locality.alternative_value
                    locality_id = hosp_locality.id
                    if hosp_locality.centroid:
                        locality_longitude = hosp_locality.centroid.x
                        locality_latitude = hosp_locality.centroid.y

            if not hosp_locality or not hosp_sublocality:
                print('failed')

            url = "%s" % (hospital.name)

            if hosp_locality and hosp_sublocality:
                url = url + "-in-%s-%s" % (sublocality_value, locality_value)

            else:
                url = url

            url = slugify(url)
            data = {}
            data['is_valid'] = True
            data['url_type'] = EntityUrls.UrlType.PAGEURL
            data['entity_type'] = 'Hospital'
            data['entity_id'] = hospital.id
            data['sitemap_identifier'] = EntityUrls.SitemapIdentifier.HOSPITAL_PAGE
            # if hosp_locality
            data['locality_id'] = locality_id
            data['locality_value'] = locality_value
            data['locality_latitude'] = locality_latitude
            data['locality_longitude'] = locality_longitude

            if locality_latitude and locality_longitude:
                data['locality_location'] = Point(locality_longitude, locality_latitude)

            if sublocality_latitude and sublocality_longitude:
                data['sublocality_location'] = Point(sublocality_longitude, sublocality_latitude)

            data['sublocality_id'] = sublocality_id
            data['sublocality_value'] = sublocality_value
            data['sublocality_latitude'] = sublocality_latitude
            data['sublocality_longitude'] = sublocality_longitude

            if hospital:
                data['location'] = hospital.location

            extras = {}
            extras['related_entity_id'] = hospital.id
            # if sublocality_id or locality_id:
            extras['location_id'] = sublocality_id if sublocality_id else locality_id
            extras['locality_value'] = locality_value if hosp_locality else ''
            extras['sublocality_value'] = sublocality_value if hosp_sublocality else ''
            extras['breadcrums'] = []
            data['extras'] = extras
            data['count'] = hospital.doctors_count if hospital.doctors_count else 0
            data['bookable_doctors_count'] = {"bookable_doctors_2km": None, "bookable_doctors_count": hospital.bookable_doctors_count if hospital.bookable_doctors_count else 0}

            new_url = url

            is_duplicate = cache.is_duplicate(new_url + '-hpp', hospital.id)

            if is_duplicate:
                new_url = new_url + '-' + str(hospital.id)

            new_url = new_url + '-hpp'
            data['url'] = new_url
            new_entity = TempURL(**data)

            cache.add(new_entity)

            to_create.append(new_entity)

        TempURL.objects.bulk_create(to_create)
        return ("success")
