from django.conf import settings
from django.db.models import Prefetch
from collections import OrderedDict
from django.template.defaultfilters import slugify
from django.contrib.gis.geos import Point
from django.db.models import Count, Max


from ondoc.api.v1.utils import RawSql
from ondoc.doctor.models import Doctor, DoctorPracticeSpecialization, Hospital, PracticeSpecialization
from ondoc.location.models import EntityUrls, TempURL

class DoctorURL():

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
        self.create_search_urls_new()
        # self.create_search_urls()
        self.create_doc_page_urls_with_hosp_details()
        self.update_breadcrumbs_without_dist_filter()
        # self.create_doctor_page_urls()
        # self.update_breadcrumbs()
        self.insert_search_urls()

    def create_search_urls_new(self):

        q1 = ''' select specialization_id, specialization, doctor_id, sublocality_value,
                locality_value, count, entity_type, url_type, is_valid, bookable_doctors_count from ( 
                select specialization_id, specialization, ROW_NUMBER() OVER (PARTITION BY doc_spec_id) AS row_num, doctor_id, sublocality_value,
                locality_value, count, entity_type, url_type, is_valid, 
                json_build_object('bookable_doctors_count',bookable_doctors_count,'bookable_doctors_2km',bookable_doctors_2km)
                as bookable_doctors_count from (                    
                select  max(dps.id) as doc_spec_id, dps.specialization_id, max(spec.name) as specialization, max(d.id) as doctor_id,
                max(h.locality) as sublocality_value, max(h.city) as locality_value, count(distinct d.id) count, ea.centroid,
                COUNT(DISTINCT CASE WHEN d.enabled_for_online_booking=True and dc.enabled_for_online_booking=True
                and h.enabled_for_online_booking=True then d.id else null END) as bookable_doctors_count,
                COUNT(DISTINCT CASE WHEN d.enabled_for_online_booking=True and dc.enabled_for_online_booking=True
                and h.enabled_for_online_booking=True 
                and ST_DWithin(ea.centroid::geography,h.location::geography,2000)then d.id else null end) as bookable_doctors_2km,
                'Doctor' as entity_type, 'SEARCHURL' url_type, True as is_valid
                from entity_address ea inner join hospital h on ((ea.type = 'LOCALITY' and lower(h.city)=lower(ea.alternative_value) and 
                ST_DWithin(ea.centroid::geography,h.location::geography,h.search_url_locality_radius)) OR 
                (ea.type = 'SUBLOCALITY' and lower(h.locality)=lower(ea.alternative_value) and ST_DWithin(ea.centroid::geography,h.location::geography,h.search_url_sublocality_radius))) and h.is_live=true
                and ea.type IN ('SUBLOCALITY' , 'LOCALITY') and ea.use_in_url=true 
                inner join doctor_clinic dc on dc.hospital_id = h.id 
                and dc.enabled=true inner join doctor d on dc.doctor_id= d.id and d.is_live=true
                inner join doctor_practice_specialization dps on dps.doctor_id = d.id 
                inner join practice_specialization spec on spec.id=dps.specialization_id
                where ea.id>=%d and ea.id<%d
                group by dps.specialization_id, ea.id having count(distinct d.id)>= %d) a)b  where row_num=1 '''

        start = self.min_ea
        to_create = []
        while start < self.max_ea:
            query = q1 % (start, start + self.step, int(settings.DOCTORS_COUNT))
            doctor_spec_data = RawSql(query, []).fetch_all()
            if doctor_spec_data:
                doctor_ids = (data.get('doctor_id') for data in doctor_spec_data)
                doc_loc_obj = Doctor.objects.prefetch_related('doctor_clinics', 'doctor_clinics__hospital').filter(id__in=doctor_ids)

                doc_loc_dict = dict()
                for doc in doc_loc_obj:
                    hospital = doc.doctor_clinics.all()[0].hospital if doc.doctor_clinics.all() else None
                    if hospital and not doc_loc_dict.get(hospital.id):
                        doc_loc_dict[doc.id] = hospital.location

                for data in doctor_spec_data:
                    location = doc_loc_dict.get(data.get('doctor_id'))
                    if location:
                        url_data = {}
                        url_data['is_valid'] = data.get('is_valid')
                        url_data['url_type'] = data.get('url_type')
                        url_data['entity_type'] = data.get('entity_type')
                        url_data['count'] = data.get('count')
                        url_data['bookable_doctors_count'] = data.get('bookable_doctors_count')
                        url_data['locality_latitude'] = location.y
                        url_data['locality_longitude'] = location.x
                        url_data['location'] = location
                        url_data['locality_location'] = location
                        url_data['locality_value'] = data.get('locality_value')
                        url_data['sitemap_identifier'] = 'DOCTORS_CITY'
                        url_data['url'] = slugify('doctors-in-' + data.get('locality_value') + '-sptcit')
                        to_create.append(TempURL(**url_data))

                        url_data['sitemap_identifier'] = 'SPECIALIZATION_CITY'
                        url_data['specialization'] = data.get('specialization')
                        url_data['specialization_id'] = data.get('specialization_id')

                        url_data['url'] = slugify(data.get('specialization') + '-in-' + data.get('locality_value') + '-sptcit')
                        to_create.append(TempURL(**url_data))

                        url_data['sitemap_identifier'] = 'SPECIALIZATION_LOCALITY_CITY'
                        url_data['sublocality_value'] = data.get('sublocality_value')
                        url_data['sublocality_latitude'] = location.y
                        url_data['sublocality_longitude'] = location.x
                        url_data['sublocality_location'] = location
                        url_data['url'] = slugify(data.get('specialization') + '-in-' + data.get('sublocality_value') + '-' + data.get('locality_value') + '-sptlitcit')
                        to_create.append(TempURL(**url_data))

                        url_data['sitemap_identifier'] = 'DOCTORS_LOCALITY_CITY'
                        url_data['specialization'] = None
                        url_data['specialization_id'] = None
                        url_data['url'] = slugify('doctors-in-' + data.get('sublocality_value') + '-' +  data.get('locality_value') + '-sptlitcit')

                        to_create.append(TempURL(**url_data))
            start = start + self.step

        TempURL.objects.bulk_create(to_create)

        update_spec_extras_query = '''update  temp_url 
                          set extras = case when sitemap_identifier='SPECIALIZATION_CITY' then
                           json_build_object('specialization_id', specialization_id, 'location_json',
                           json_build_object('locality_id', locality_id, 'locality_value', locality_value, 'locality_latitude', 
                           locality_latitude,'locality_longitude', locality_longitude), 'specialization', specialization)

                          else  json_build_object('specialization_id', specialization_id,'location_json',
                          json_build_object('sublocality_id',sublocality_id,'sublocality_value',sublocality_value,
                           'locality_id', locality_id, 'locality_value', locality_value,
                           'breadcrum_url',slugify_url(specialization || '-in-' || locality_value ||'-sptcit'),
                          'sublocality_latitude',sublocality_latitude, 'sublocality_longitude',sublocality_longitude, 
                          'locality_latitude',locality_latitude,'locality_longitude',locality_longitude),'specialization', specialization) end
                          where sitemap_identifier in ('SPECIALIZATION_LOCALITY_CITY','SPECIALIZATION_CITY')'''
        update_spec_extras = RawSql(update_spec_extras_query, []).execute()

        update_extras_query = '''update  temp_url 
                               set extras = case when sitemap_identifier='DOCTORS_CITY' then
                               json_build_object('location_json',json_build_object('locality_id',locality_id,'locality_value',locality_value, 
                               'locality_latitude',locality_latitude,'locality_longitude',locality_longitude))

                               else json_build_object('location_json',
                               json_build_object('sublocality_id', sublocality_id,'sublocality_value', sublocality_value,
                               'locality_id', locality_id, 'locality_value', locality_value,'breadcrum_url',slugify_url('doctors-in-' || locality_value ||'-sptcit'),
                               'sublocality_latitude',sublocality_latitude, 'sublocality_longitude',sublocality_longitude, 'locality_latitude',locality_latitude,
                               'locality_longitude',locality_longitude))  end
                                where sitemap_identifier in ('DOCTORS_LOCALITY_CITY','DOCTORS_CITY')'''
        update_extras = RawSql(update_extras_query, []).execute()


        # clean up duplicate urls
        RawSql('''delete from temp_url where id in (select id from 
                (select eu.*, row_number() over(partition by url ) rownum from temp_url eu  
                )x where rownum>1
                ) ''', []).execute()
        return 'success'

    def create_doc_page_urls_with_hosp_details(self):

        sequence = self.sequence

        cache = PageUrlCache(EntityUrls.SitemapIdentifier.DOCTOR_PAGE)
        spec_cache = SpecializationCache()
        to_create = []

        doc_obj = Doctor.objects.prefetch_related('doctorpracticespecializations',
                                                  'doctorpracticespecializations__specialization',
                                                  (Prefetch('hospitals',
                                                            queryset=Hospital.objects.filter(is_live=True).order_by(
                                                                'hospital_type', 'id')))
                                                  ).filter(is_live=True, is_test_doctor=False).order_by('id')

        for doctor in doc_obj:
            locality_value = None
            locality_latitude = None
            locality_longitude = None
            sublocality_value = None
            sublocality_longitude = None
            sublocality_latitude = None
            sequence = sequence
            hospital = None

            practice_specializations = doctor.doctorpracticespecializations.all()
            sp_dict = dict()
            for sp in practice_specializations:
                sp_dict[sp.specialization_id] = sp.specialization.name
            sp_dict = OrderedDict(sorted(sp_dict.items()))
            specializations = list(sp_dict.values())
            specialization_ids = list(sp_dict.keys())

            all_hospitals = doctor.hospitals.all()
            for hosp in all_hospitals:
                if hosp.is_live:
                    hospital = hosp
                break

            top_specialization = None
            if practice_specializations:
                top_specialization = practice_specializations.order_by('specialization__breadcrumb_priority').first()

            if not hospital:
                print('hospital not found')

            if hospital:
                sublocality_value = hospital.locality
                sublocality_longitude = hospital.location.x if hospital.location else None
                sublocality_latitude = hospital.location.y if hospital.location else None
                locality_value = hospital.city
                locality_longitude = hospital.location.x if hospital.location else None
                locality_latitude = hospital.location.y if hospital.location else None

            if specializations:
                url = "dr-%s-%s" % (doctor.name, "-".join(specializations))
            else:
                url = "dr-%s" % (doctor.name)

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
            data['entity_type'] = 'Doctor'
            data['entity_id'] = doctor.id
            data['sitemap_identifier'] = EntityUrls.SitemapIdentifier.DOCTOR_PAGE
            # if doc_locality
            data['locality_id'] = None
            data['locality_value'] = locality_value
            data['locality_latitude'] = locality_latitude
            data['locality_longitude'] = locality_longitude

            if locality_latitude and locality_longitude:
                data['locality_location'] = Point(locality_longitude, locality_latitude)

            if sublocality_latitude and sublocality_longitude:
                data['sublocality_location'] = Point(sublocality_longitude, sublocality_latitude)

            data['sublocality_id'] = None
            data['sublocality_value'] = sublocality_value
            data['sublocality_latitude'] = sublocality_latitude
            data['sublocality_longitude'] = sublocality_longitude

            if hospital:
                data['location'] = hospital.location

            extras = {}
            extras['related_entity_id'] = doctor.id
            extras['location_id'] = None
            extras['locality_value'] = locality_value if locality_value else ''
            extras['sublocality_value'] = sublocality_value if sublocality_value else ''
            extras['breadcrums'] = []
            data['extras'] = extras
            if top_specialization:
                data['specialization'] = top_specialization.specialization.name
                data['specialization_id'] = top_specialization.specialization.id

            new_url = url

            is_duplicate = cache.is_duplicate(new_url + '-dpp', doctor.id)

            if is_duplicate:
                new_url = new_url + '-' + str(doctor.id)

            new_url = new_url + '-dpp'

            data['url'] = new_url
            new_entity = TempURL(**data)

            cache.add(new_entity)

            to_create.append(new_entity)

        TempURL.objects.bulk_create(to_create)
        return ("success")

    def insert_search_urls(self):

        seq = self.sequence

        query = '''insert into entity_urls(sequence,extras, sitemap_identifier, url, count, entity_type, 
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
                  ''' %seq


        update_query = '''update entity_urls set is_valid=false where sitemap_identifier 
                           in ('DOCTORS_LOCALITY_CITY', 'DOCTORS_CITY', 'SPECIALIZATION_CITY', 
                           'SPECIALIZATION_LOCALITY_CITY','DOCTOR_PAGE') and sequence< %d''' % seq

        
        cleanup = '''delete from entity_urls where id in (select id from 
        (select eu.*, row_number() over(partition by url order by is_valid desc, sequence desc) rownum from entity_urls eu  
        )x where rownum>1
        ) '''

        RawSql(query, []).execute()
        RawSql(update_query, []).execute()
        RawSql(cleanup, []).execute()


        # from django.db import connection
        # with connection.cursor() as cursor:
        #     try:
        #         cursor.execute(query)
        #         cursor.execute(update_query)
        #     except Exception as e:
        #         print(str(e))
        #         return False

        return True


    def create_search_urls(self):

        q1 = '''insert into temp_url (specialization_id, search_slug, count, sublocality_id, locality_id, 
                    sitemap_identifier, entity_type, url_type, is_valid, created_at, updated_at,bookable_doctors_count )
                   select specialization_id, search_slug, count, sublocality_id,locality_id,sitemap_identifier,
                    entity_type, url_type, is_valid, now(), now(),
                    json_build_object('bookable_doctors_count',bookable_doctors_count,'bookable_doctors_2km',bookable_doctors_2km)
                    as bookable_doctors_count
                    from (                    
                    select  dps.specialization_id,search_slug, count(distinct d.id) count, ea.centroid,
                    COUNT(DISTINCT CASE WHEN d.enabled_for_online_booking=True and dc.enabled_for_online_booking=True
                    and h.enabled_for_online_booking=True then d.id else null END) as bookable_doctors_count,
                    COUNT(DISTINCT CASE WHEN d.enabled_for_online_booking=True and dc.enabled_for_online_booking=True
                    and h.enabled_for_online_booking=True 
                    and ST_DWithin(ea.centroid::geography,h.location::geography,2000)then d.id else null end) as bookable_doctors_2km,
                    case when ea.type = 'SUBLOCALITY' then ea.id end as sublocality_id,
                    case when ea.type = 'LOCALITY' then ea.id end as locality_id,
                    case when ea.type = 'LOCALITY' then 'SPECIALIZATION_CITY' else 'SPECIALIZATION_LOCALITY_CITY' end as sitemap_identifier,
                    'Doctor' as entity_type, 'SEARCHURL' url_type, True as is_valid
                    from entity_address ea inner join hospital h on ((ea.type = 'LOCALITY' and 
                    ST_DWithin(ea.centroid::geography,h.location::geography,15000)) OR 
                    (ea.type = 'SUBLOCALITY' and ST_DWithin(ea.centroid::geography,h.location::geography,5000))) and h.is_live=true
                    and ea.type IN ('SUBLOCALITY' , 'LOCALITY') and ea.use_in_url=true 
                    inner join doctor_clinic dc on dc.hospital_id = h.id 
                    and dc.enabled=true inner join doctor d on dc.doctor_id= d.id and d.is_live=true
                    inner join doctor_practice_specialization dps on dps.doctor_id = d.id 
                    where ea.id>=%d and ea.id<%d
                    group by dps.specialization_id, ea.id having count(distinct d.id)>=3) a'''

        q2 = '''insert into temp_url (search_slug, count, sublocality_id, locality_id, 
                      sitemap_identifier, entity_type, url_type, is_valid, created_at, updated_at, bookable_doctors_count)
                      
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
                    case when ea.type = 'LOCALITY' then 'DOCTORS_CITY' else 'DOCTORS_LOCALITY_CITY' end as sitemap_identifier,
                    'Doctor' as entity_type, 'SEARCHURL' url_type, True as is_valid, now(), now()
                    from entity_address ea inner join hospital h on ((ea.type = 'LOCALITY' and 
                    ST_DWithin(ea.centroid::geography,h.location::geography,15000)) OR 
                    (ea.type = 'SUBLOCALITY' and ST_DWithin(ea.centroid::geography,h.location::geography,5000))) and h.is_live=true
                    and ea.type IN ('SUBLOCALITY' , 'LOCALITY') and ea.use_in_url=true 
                    inner join doctor_clinic dc on dc.hospital_id = h.id 
                    and dc.enabled=true inner join doctor d on dc.doctor_id= d.id and d.is_live=true
                    where ea.id>=%d and ea.id<%d
                    group by ea.id having count(distinct d.id)>=3)a'''

        start = self.min_ea
        while start < self.max_ea:
            query = q1 % (start, start + self.step)
            RawSql(query, []).execute()
            query = q2 % (start, start + self.step)
            RawSql(query, []).execute()

            start = start + self.step


        RawSql('''update temp_url tu set locality_id = (select parent_id from entity_address where id = tu.sublocality_id)
                where locality_id is null and sublocality_id is not null''', []).execute()


        RawSql('''delete from temp_url where locality_id is null''', []).execute()

        RawSql('''delete from temp_url where locality_id in (select id from entity_address where use_in_url is false)''', []).execute()

        RawSql('''delete from temp_url where sublocality_id in (select id from entity_address where use_in_url is false)''', []).execute()

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

        RawSql('''UPDATE temp_url SET specialization = ps.name
                FROM practice_specialization ps WHERE specialization_id = ps.id''', []).execute()        


        RawSql('''update temp_url set location = sublocality_location where sublocality_location is not null''', []).execute()        

        RawSql('''update temp_url set location = locality_location where location is null''', []).execute()        


        #return 




        # create_spec_temp_table_query = '''insert into temp_url
        #             (specialization_id, specialization, search_slug, url, extras,locality_location,sublocality_location,
        #              location, count, sublocality_id, locality_id, sublocality_longitude, sublocality_latitude,
        #              locality_longitude, locality_latitude, sublocality_value, locality_value, sitemap_identifier,
        #              entity_type, url_type, is_valid, created_at, updated_at )
        #             select 
        #             ps.id as specialization_id, ps.name as specialization,
        #             ea.search_slug, null as url, null::json as extras, null::geography as locality_location, 
        #             null::geography as sublocality_location, null::geography as location,
        #             count(distinct d.id) as count,
        #             case when ea.type = 'SUBLOCALITY' then 
        #             ea.id 
        #             end as sublocality_id,
        #             case when ea.type = 'LOCALITY' then ea.id 
        #             when ea.type = 'SUBLOCALITY' then max(eaparent.id)
        #             end as locality_id,
        #             case when ea.type = 'SUBLOCALITY' then 
        #             st_x(ea.centroid::geometry) end as sublocality_longitude,
        #             case when ea.type = 'SUBLOCALITY' then 
        #             st_y(ea.centroid::geometry) end as sublocality_latitude,
        #             case when ea.type = 'LOCALITY' then st_x(ea.centroid::geometry)
        #             when ea.type = 'SUBLOCALITY' then max(st_x(eaparent.centroid::geometry))
        #             end as locality_longitude,
        #             case when ea.type = 'LOCALITY' then st_y(ea.centroid::geometry)
        #             when ea.type = 'SUBLOCALITY' then max(st_y(eaparent.centroid::geometry))
        #             end as locality_latitude,
        #             case when ea.type = 'SUBLOCALITY' then ea.alternative_value end as sublocality_value,
        #             case when ea.type = 'LOCALITY' then ea.alternative_value 
        #              when  ea.type = 'SUBLOCALITY' then max(eaparent.alternative_value) end as locality_value,
        #             case when ea.type = 'LOCALITY' then 'SPECIALIZATION_CITY'
        #             else 'SPECIALIZATION_LOCALITY_CITY' end as sitemap_identifier,
        #             'Doctor' as entity_type,
        #             'SEARCHURL' url_type,
        #             True as is_valid, now(), now()
        #             from hospital h inner join entity_address ea on ((ea.type = 'LOCALITY' and 
        #             ST_DWithin(ea.centroid,h.location,15000)) OR 
        #             (ea.type = 'SUBLOCALITY' and ST_DWithin(ea.centroid,h.location,5000))) and h.is_live=true
        #             and ea.type IN ('SUBLOCALITY' , 'LOCALITY') and ea.use_in_url=true inner join doctor_clinic dc on dc.hospital_id = h.id
        #             and dc.enabled=true
        #             inner join doctor d on dc.doctor_id= d.id
        #             inner join doctor_practice_specialization dps on dps.doctor_id = d.id and d.is_live=true
        #             inner join practice_specialization ps on ps.id = dps.specialization_id 
        #             left join entity_address eaparent on ea.parent_id=eaparent.id and eaparent.use_in_url=true
        #             group by ps.id, ea.id having count(distinct d.id) >= 3 
        #         ''' 
        # create_spec_temp_table = RawSql(create_spec_temp_table_query, []).execute()

        # create_temp_table_query = '''insert into temp_url( search_slug,url, count,
        #             sublocality_id, locality_id, sublocality_longitude, sublocality_latitude, locality_longitude, 
        #             locality_latitude, sublocality_value, locality_value, sitemap_identifier, entity_type, url_type,
        #             is_valid, created_at, updated_at )
        #             select 
        #             ea.search_slug, 
        #             case when ea.type = 'SUBLOCALITY' then 
        #             slugify_url(concat('doctors-in-', ea.search_slug, '-sptlitcit'))
        #             else slugify_url(concat('doctors-in-', ea.search_slug, '-sptcit'))
        #             end as url, count(distinct d.id) as count,
        #             case when ea.type = 'SUBLOCALITY' then 
        #             ea.id 
        #             end as sublocality_id,
        #             case when ea.type = 'LOCALITY' then ea.id 
        #             when ea.type = 'SUBLOCALITY' then max(eaparent.id)
        #             end as locality_id,
        #             case when ea.type = 'SUBLOCALITY' then 
        #             st_x(ea.centroid::geometry) end as sublocality_longitude,
        #             case when ea.type = 'SUBLOCALITY' then 
        #             st_y(ea.centroid::geometry) end as sublocality_latitude,
        #             case when ea.type = 'LOCALITY' then st_x(ea.centroid::geometry)
        #             when ea.type = 'SUBLOCALITY' then max(st_x(eaparent.centroid::geometry))
        #             end as locality_longitude,
        #             case when ea.type = 'LOCALITY' then st_y(ea.centroid::geometry)
        #             when ea.type = 'SUBLOCALITY' then max(st_y(eaparent.centroid::geometry)) 
        #             end as locality_latitude,
        #             case when ea.type = 'SUBLOCALITY' then ea.alternative_value end as sublocality_value,
        #             case when ea.type = 'LOCALITY' then ea.alternative_value 
        #             when  ea.type = 'SUBLOCALITY' then max(eaparent.alternative_value) end as locality_value,
        #             case when ea.type = 'LOCALITY' then 'DOCTORS_CITY'
        #             else 'DOCTORS_LOCALITY_CITY' end as sitemap_identifier,                    
        #             'Doctor' as entity_type,
        #             'SEARCHURL' url_type,
        #             True as is_valid, now(), now()
        #             from hospital h inner join entity_address ea on ((ea.type = 'LOCALITY' and ST_DWithin(ea.centroid,h.location,15000)) OR 
        #             (ea.type = 'SUBLOCALITY' and ST_DWithin(ea.centroid,h.location,5000))) and h.is_live=true
        #             and ea.type IN ('SUBLOCALITY' , 'LOCALITY') and ea.use_in_url=true inner join doctor_clinic dc on dc.hospital_id = h.id
        #             and dc.enabled=true 
        #             inner join doctor d on dc.doctor_id= d.id
        #             and d.is_live=true left join entity_address eaparent on ea.parent_id=eaparent.id and eaparent.use_in_url=true
        #             group by ea.id having count(distinct d.id) >= 3'''
        # create_temp_table = RawSql(create_temp_table_query, []).execute()

        update_urls_query = '''update temp_url set url = case when sitemap_identifier = 'SPECIALIZATION_LOCALITY_CITY' then 
                    slugify_url(concat(specialization,'-in-', search_slug, '-sptlitcit'))
                    else slugify_url(concat(specialization,'-in-', search_slug, '-sptcit'))
                    end where sitemap_identifier in ('SPECIALIZATION_LOCALITY_CITY','SPECIALIZATION_CITY')'''
        update_urls = RawSql(update_urls_query, []).execute()


        update_urls_query = '''update temp_url set url = case when sitemap_identifier = 'DOCTORS_CITY' then 
                    slugify_url(concat('doctors-in-', search_slug, '-sptcit'))
                    else slugify_url(concat('doctors-in-', search_slug, '-sptlitcit'))
                    end where sitemap_identifier in ('DOCTORS_LOCALITY_CITY','DOCTORS_CITY')'''
        update_urls = RawSql(update_urls_query, []).execute()

        update_spec_extras_query = '''update  temp_url 
                          set extras = case when sitemap_identifier='SPECIALIZATION_CITY' then
                           json_build_object('specialization_id', specialization_id, 'location_json',
                           json_build_object('locality_id', locality_id, 'locality_value', locality_value, 'locality_latitude', 
                           locality_latitude,'locality_longitude', locality_longitude), 'specialization', specialization)

                          else  json_build_object('specialization_id', specialization_id,'location_json',
                          json_build_object('sublocality_id',sublocality_id,'sublocality_value',sublocality_value,
                           'locality_id', locality_id, 'locality_value', locality_value,
                           'breadcrum_url',slugify_url(specialization || '-in-' || locality_value ||'-sptcit'),
                          'sublocality_latitude',sublocality_latitude, 'sublocality_longitude',sublocality_longitude, 
                          'locality_latitude',locality_latitude,'locality_longitude',locality_longitude),'specialization', specialization) end
                          where sitemap_identifier in ('SPECIALIZATION_LOCALITY_CITY','SPECIALIZATION_CITY')'''
        update_spec_extras = RawSql(update_spec_extras_query, []).execute()

        update_extras_query = '''update  temp_url 
                               set extras = case when sitemap_identifier='DOCTORS_CITY' then
                               json_build_object('location_json',json_build_object('locality_id',locality_id,'locality_value',locality_value, 
                               'locality_latitude',locality_latitude,'locality_longitude',locality_longitude))

                               else json_build_object('location_json',
                               json_build_object('sublocality_id', sublocality_id,'sublocality_value', sublocality_value,
                               'locality_id', locality_id, 'locality_value', locality_value,'breadcrum_url',slugify_url('doctors-in-' || locality_value ||'-sptcit'),
                               'sublocality_latitude',sublocality_latitude, 'sublocality_longitude',sublocality_longitude, 'locality_latitude',locality_latitude,
                               'locality_longitude',locality_longitude))  end
                                where sitemap_identifier in ('DOCTORS_LOCALITY_CITY','DOCTORS_CITY')'''
        update_extras = RawSql(update_extras_query, []).execute()

        # update_locality_loc_query = '''update temp_url set locality_location = st_setsrid(st_point(locality_longitude, locality_latitude),4326)::geography where 
        #         locality_latitude is not null and locality_longitude is not null'''

        # update_locality_loc = RawSql(update_locality_loc_query, []).execute()

        # update_sublocality_loc_query = '''update temp_url set sublocality_location = st_setsrid(st_point(sublocality_longitude, sublocality_latitude),4326)::geography where 
        #          sublocality_latitude is not null and sublocality_longitude is not null'''

        # update_sublocality_loc = RawSql(update_sublocality_loc_query, []).execute()

        # update_location_query = '''update temp_url set location = case when 
        #                    sublocality_location is not null then sublocality_location  else locality_location end'''
        # update_location = RawSql(update_location_query, []).execute()

        #clean up duplicate urls
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

        #update for speciality city
        RawSql('''update temp_url tu set breadcrumb=(select json_build_array(json_build_object('title', locality_value, 'url', url, 'link_title', concat('Doctors in ',locality_value))) 
            from temp_url where sitemap_identifier ='DOCTORS_CITY' and lower(locality_value)=lower(tu.locality_value)
            and st_dwithin(location::geography, tu.location::geography, 20000) order by st_distance(location, tu.location) asc limit 1)
            where sitemap_identifier ='SPECIALIZATION_CITY' ''', []).execute()

        RawSql('''update temp_url tu set breadcrumb=(select json_build_array(json_build_object('title', locality_value, 'url', url, 'link_title', concat('Doctors in ',locality_value))) 
                   from temp_url where sitemap_identifier ='DOCTORS_CITY' and lower(locality_value)=lower(tu.locality_value)
                   and st_dwithin(location::geography, tu.location::geography, 20000) order by st_distance(location, tu.location) asc limit 1)
                   where sitemap_identifier ='DOCTORS_LOCALITY_CITY' ''', []).execute()

        #update for speciality locality city
        RawSql('''update temp_url tu set breadcrumb = (select  breadcrumb || jsonb_build_array(jsonb_build_object('title', specialization, 'url', url, 'link_title', concat(specialization, ' in ', locality_value)))
            from temp_url  where sitemap_identifier ='SPECIALIZATION_CITY' and lower(locality_value)=lower(tu.locality_value)
            and specialization_id = tu.specialization_id
            and st_dwithin(location::geography, tu.location::geography, 20000) order by st_distance(location, tu.location) asc limit 1) 
            where sitemap_identifier ='SPECIALIZATION_LOCALITY_CITY' 
            ''', []).execute()

        #update for doctor profile
        RawSql('''update temp_url tu set breadcrumb = (select  breadcrumb || 
            jsonb_build_array(jsonb_build_object('title', concat(sublocality_value,' ',locality_value), 'url', url, 'link_title', concat(specialization, ' in ', sublocality_value,' ',locality_value) ))
            from temp_url  where sitemap_identifier ='SPECIALIZATION_LOCALITY_CITY' and lower(locality_value)=lower(tu.locality_value)
            and lower(sublocality_value)=lower(tu.sublocality_value) and specialization_id = tu.specialization_id
            and st_dwithin(location::geography, tu.location::geography, 10000) order by st_distance(location, tu.location) asc limit 1) 
            where sitemap_identifier ='DOCTOR_PAGE' ''', []).execute()

        #update for doctor profile from city speciality if null
        RawSql('''update temp_url tu set breadcrumb = (select  breadcrumb 
            from temp_url  where sitemap_identifier ='SPECIALIZATION_CITY' and lower(locality_value)=lower(tu.locality_value)
            and specialization_id = tu.specialization_id
            and st_dwithin(location::geography, tu.location::geography, 20000) order by st_distance(location, tu.location) asc limit 1) 
            where sitemap_identifier ='DOCTOR_PAGE' and breadcrumb is null ''', []).execute()

        #update for doctor profile from city if null
        RawSql('''update temp_url tu set breadcrumb = (select  breadcrumb 
            from temp_url  where sitemap_identifier ='DOCTORS_CITY' and lower(locality_value)=lower(tu.locality_value)
            and st_dwithin(location::geography, tu.location::geography, 20000) order by st_distance(location, tu.location) asc limit 1) 
            where sitemap_identifier ='DOCTOR_PAGE' and breadcrumb is null ''', []).execute()

        RawSql('''update temp_url tu set breadcrumb=json_build_array() where breadcrumb is null ''', []).execute()


    def update_breadcrumbs_without_dist_filter(self):

        # set breadcrumbs to default empty array
        RawSql('''update temp_url tu set breadcrumb=json_build_array()''', []).execute()

        #update for speciality city
        RawSql('''update temp_url tu set breadcrumb=(select json_build_array(json_build_object('title', locality_value, 'url', url, 'link_title', concat('Doctors in ',locality_value))) 
            from temp_url where sitemap_identifier ='DOCTORS_CITY' and lower(locality_value)=lower(tu.locality_value)
             order by st_distance(location, tu.location) asc limit 1)
            where sitemap_identifier ='SPECIALIZATION_CITY' ''', []).execute()

        RawSql('''update temp_url tu set breadcrumb=(select json_build_array(json_build_object('title', locality_value, 'url', url, 'link_title', concat('Doctors in ',locality_value))) 
                   from temp_url where sitemap_identifier ='DOCTORS_CITY' and lower(locality_value)=lower(tu.locality_value)
                    order by st_distance(location, tu.location) asc limit 1)
                   where sitemap_identifier ='DOCTORS_LOCALITY_CITY' ''', []).execute()

        #update for speciality locality city
        RawSql('''update temp_url tu set breadcrumb = (select  breadcrumb || jsonb_build_array(jsonb_build_object('title', specialization, 'url', url, 'link_title', concat(specialization, ' in ', locality_value)))
            from temp_url  where sitemap_identifier ='SPECIALIZATION_CITY' and lower(locality_value)=lower(tu.locality_value)
            and specialization_id = tu.specialization_id order by st_distance(location, tu.location) asc limit 1) 
            where sitemap_identifier ='SPECIALIZATION_LOCALITY_CITY' 
            ''', []).execute()

        #update for doctor profile
        RawSql('''update temp_url tu set breadcrumb = (select  breadcrumb || 
            jsonb_build_array(jsonb_build_object('title', sublocality_value, 'url', url, 'link_title', concat(specialization, ' in ', sublocality_value,' ',locality_value) ))
            from temp_url  where sitemap_identifier ='SPECIALIZATION_LOCALITY_CITY' and lower(locality_value)=lower(tu.locality_value)
            and lower(sublocality_value)=lower(tu.sublocality_value) and specialization_id = tu.specialization_id
             order by st_distance(location, tu.location) asc limit 1) 
            where sitemap_identifier ='DOCTOR_PAGE' ''', []).execute()

        #update for doctor profile from city speciality if null
        RawSql('''update temp_url tu set breadcrumb = (select  breadcrumb || 
            jsonb_build_array(jsonb_build_object('title', locality_value, 'url', url, 'link_title', concat(specialization, ' in ', locality_value) ))
            from temp_url  where sitemap_identifier ='SPECIALIZATION_CITY' and lower(locality_value)=lower(tu.locality_value)
            and specialization_id = tu.specialization_id order by st_distance(location, tu.location) asc limit 1) 
            where sitemap_identifier ='DOCTOR_PAGE' and breadcrumb is null ''', []).execute()

        #update for doctor profile from locality city if null
        RawSql('''update temp_url tu set breadcrumb = (select  breadcrumb 
            from temp_url  where sitemap_identifier ='DOCTORS_LOCALITY_CITY' and lower(locality_value)=lower(tu.locality_value)
              and lower(sublocality_value)=lower(tu.sublocality_value) order by st_distance(location, tu.location) asc limit 1) 
            where sitemap_identifier ='DOCTOR_PAGE' and breadcrumb is null ''', []).execute()

        # update for doctor profile from city if null
        RawSql('''update temp_url tu set breadcrumb = (select  breadcrumb 
                    from temp_url  where sitemap_identifier ='DOCTORS_CITY' and lower(locality_value)=lower(tu.locality_value)
                     order by st_distance(location, tu.location) asc limit 1) 
                    where sitemap_identifier ='DOCTOR_PAGE' and breadcrumb is null ''', []).execute()

        RawSql('''update temp_url tu set breadcrumb=json_build_array() where breadcrumb is null ''', []).execute()

    def create_doctor_page_urls(self):


        sequence = self.sequence

        cache = PageUrlCache(EntityUrls.SitemapIdentifier.DOCTOR_PAGE)
        spec_cache = SpecializationCache()
        #to_disable = []
        #to_delete = []
        to_create = []

        doc_obj =Doctor.objects.prefetch_related('doctorpracticespecializations', 'doctorpracticespecializations__specialization',
                                    (Prefetch('hospitals', queryset=Hospital.objects.filter(is_live=True).order_by('hospital_type', 'id')))
                                    ).prefetch_related('hospitals__entity','hospitals__entity__location','hospitals__entity__location__parent').filter(is_live=True, is_test_doctor=False).order_by('id')


        for doctor in doc_obj:
            #status = DoctorPageURL.create_doctor_page_urls(doctor,sequence)

            locality_value = None
            locality_id = None
            locality_latitude = None
            locality_longitude = None
            sublocality_value = None
            sublocality_id = None
            sublocality_longitude = None
            sublocality_latitude = None
            sequence = sequence
            doc_sublocality = None
            doc_locality = None
            hospital = None

	        #practice_specializations = doctor.doctorpracticespecializations.all().order_by('specialization__breadcrumb_priority')
            #sp_dict = OrderedDict()
            #for sp in practice_specializations:
            #    sp_dict[sp.specialization_id] = sp.specialization.name

            practice_specializations = doctor.doctorpracticespecializations.all()
            sp_dict = dict()
            for sp in practice_specializations:
                sp_dict[sp.specialization_id] = sp.specialization.name
            sp_dict = OrderedDict(sorted(sp_dict.items()))
            specializations = list(sp_dict.values())
            specialization_ids = list(sp_dict.keys())

            all_hospitals = doctor.hospitals.all()
            for hosp in all_hospitals:
                if hosp.is_live:
                    hospital = hosp
                break

            top_specialization = None
            if practice_specializations:
                top_specialization = practice_specializations.order_by('specialization__breadcrumb_priority').first()

            # top_specialization = None
            # for ps in practice_specializations:
            #     spec = spec_cache.get(ps.specialization_id)
            #     if not top_specialization:
            #         top_specialization = spec
            #     elif spec and spec.get('doctor_count')> top_specialization.get('doctor_count'):
            #         top_specialization = spec

            #print(top_specialization)



            #print('attempting for doctor '+str(doctor.id))
            # if doctor.hospitals.all():
            #     hospital = doctor.hospitals.all()[0]
            #     if hospital.is_live:
                    # doc_sublocality = hospital.entity.filter(type="SUBLOCALITY").first()
            if not hospital:
                print('hospital not found')

            if hospital:
                entity_location_relation = hospital.entity.all()
                print('mapped entities for hospital'+str(hospital.id)+'='+str(len(entity_location_relation)))
                for obj in entity_location_relation:
                    #print('location mapped')

                    if not doc_sublocality and obj.location.use_in_url:
                        if obj.location.type =='SUBLOCALITY':
                            doc_sublocality = obj.location
                            #print('sublocality found')

                    # if not doc_locality and obj.location.use_in_url:
                    #     if obj.location.type =='LOCALITY':
                    #         doc_locality = obj.location

                    # if obj.location.type =='SUBLOCALITY':
                    #
                    #     doc_sublocality = EntityAddress.objects.filter(id=obj.location.id)
                    #     if doc_sublocality:
                    #         doc_sublocality = doc_sublocality[0]
                if doc_sublocality:
                    sublocality_value = doc_sublocality.alternative_value
                    sublocality_id = doc_sublocality.id
                    if doc_sublocality.centroid:
                        sublocality_longitude = doc_sublocality.centroid.x
                        sublocality_latitude = doc_sublocality.centroid.y
                    # doc_sublocality = hospital.entity.filter(type="LOCALITY", valid=True).first()

                    #doc_locality = EntityAddress.objects.filter(id=doc_sublocality.parent).first()
                    doc_locality = doc_sublocality.parent
                    if doc_locality:
                        #doc_locality = doc_locality[0]
                        locality_value = doc_locality.alternative_value
                        locality_id = doc_locality.id
                        if doc_locality.centroid:
                            locality_longitude = doc_locality.centroid.x
                            locality_latitude = doc_locality.centroid.y
                    #doc_locality = EntityAddress.objects.filter(id=doc_sublocality.location.parent).first()
                    # locality_value = doc_locality.alternative_value
                    # locality_id = doc_locality.id
                    # if doc_locality.centroid:
                    #     locality_longitude = doc_locality.centroid.x
                    #     locality_latitude = doc_locality.centroid.y

                    # doc_locality = hospital.entity.filter(type="LOCALITY", valid=True).first()
                    #doc_locality = hospital.entity.filter(type="LOCALITY", valid=True, location__centroid__isnull=False).first()

            if not doc_locality or not doc_sublocality:
                print('failed')

            if specializations:
                url = "dr-%s-%s" % (doctor.name, "-".join(specializations))
            else:
                url = "dr-%s" % (doctor.name)

            if doc_locality and doc_sublocality:
                url = url + "-in-%s-%s" % (sublocality_value, locality_value)
            # elif doc_locality:
            #     url = url + "-in-%s" % (locality_value)
            else:
                url = url

            url = slugify(url)
            data = {}
            data['is_valid'] = True
            data['url_type'] = EntityUrls.UrlType.PAGEURL
            data['entity_type'] = 'Doctor'
            data['entity_id'] = doctor.id
            data['sitemap_identifier'] = EntityUrls.SitemapIdentifier.DOCTOR_PAGE
            #if doc_locality
            data['locality_id'] = locality_id
            data['locality_value'] = locality_value
            data['locality_latitude'] = locality_latitude
            data['locality_longitude'] = locality_longitude

            if locality_latitude and locality_longitude:
                data['locality_location'] = Point(locality_longitude, locality_latitude)

            if sublocality_latitude and sublocality_longitude:
                data['sublocality_location'] = Point(sublocality_longitude, sublocality_latitude)

            #if doc_sublocality:
            data['sublocality_id'] = sublocality_id
            data['sublocality_value'] = sublocality_value
            data['sublocality_latitude'] = sublocality_latitude
            data['sublocality_longitude'] = sublocality_longitude

            if hospital:
                data['location'] = hospital.location

            # if specializations and specialization_ids:
            #     data['specialization'] = specializations[0]
            #     data['specialization_id'] = specialization_ids[0]

            extras = {}
            extras['related_entity_id'] = doctor.id
            #if sublocality_id or locality_id:
            extras['location_id'] = sublocality_id if sublocality_id else locality_id
            extras['locality_value'] = locality_value if doc_locality else ''
            extras['sublocality_value'] = sublocality_value if doc_sublocality else ''
            extras['breadcrums'] = []
            data['extras'] = extras
            if top_specialization:
                data['specialization'] = top_specialization.specialization.name
                data['specialization_id'] = top_specialization.specialization.id

            #data['sequence'] = sequence

            new_url = url
            # counter = 0
            #
            # while True:
            #     if counter>0:
            #         # new_url = url+'-'+'-'+''.join([random.choice(string.digits) for n in range(10)])
            #         new_url = url + '-' + str(counter)
            #     dup_url = EntityUrls.objects.filter(url=new_url, sitemap_identifier=EntityUrls.SitemapIdentifier.DOCTOR_PAGE).filter(~Q(entity_id=doctor.id)).first()
            #     if not dup_url:
            #         break
            #     counter = counter + 1

            is_duplicate = cache.is_duplicate(new_url + '-dpp', doctor.id)
            # dup_url = EntityUrls.objects.filter(url=new_url + '-dpp',
            #                                     sitemap_identifier=EntityUrls.SitemapIdentifier.DOCTOR_PAGE
            #                                     ).filter(~Q(entity_id=doctor.id)).first()
            if is_duplicate:
                new_url = new_url + '-' + str(doctor.id)

            new_url = new_url + '-dpp'

            # EntityUrls.objects.filter(entity_id=doctor.id,
            #                           sitemap_identifier=EntityUrls.SitemapIdentifier.DOCTOR_PAGE).filter(
            #     ~Q(url=new_url)).update(is_valid=False)

            #to_delete.extend(cache.get_deletions(new_url, doctor.id))
            # EntityUrls.objects.filter(entity_id=doctor.id, sitemap_identifier=EntityUrls.SitemapIdentifier.DOCTOR_PAGE,
            #                           url=new_url).delete()

            data['url'] = new_url
            new_entity = TempURL(**data)

            cache.add(new_entity)

            to_create.append(new_entity)
            #EntityUrls.objects.create(**data)

            #with transaction.atomic():

            #EntityUrls.objects.filter(id__in=to_delete).delete()
            #EntityUrls.filter(id__in=to_delete).delete()
            #EntityUrls.objects.filter(sitemap_identifier='DOCTOR_PAGE', sequence__lt=sequence).update(is_valid=False)
        TempURL.objects.bulk_create(to_create)
        return ("success")

class SpecializationCache():

    def __init__(self):
        qs = DoctorPracticeSpecialization.objects.values('specialization_id').annotate(doctor_count=Count('doctor'), name=Max('specialization__name'))
        self.cache = dict()
        for sp in qs:
            self.cache[sp.get('specialization_id')] = sp

    def get(self, specialization_id):
        return self.cache.get(specialization_id)


class PageUrlCache():

    def __init__(self, sitemap_identifier):
        self.url_cache = dict()
        self.entity_cache = dict()

        existing = EntityUrls.objects.filter(sitemap_identifier=sitemap_identifier)

        for ex in existing:
            self.add(ex)
            # if not self.url_cache.get(ex.url):
            #     self.url_cache[ex.url] = []

            # if not self.entity_cache.get(ex.id):
            #     self.entity_cache[ex.id] = []

            # self.url_cache[ex.url].append({'id':ex.entity_id})
            # self.entity_cache[ex.id].append({'url':ex.url})


    def is_duplicate(self, url, entity_id):
        entities = self.url_cache.get(url)
        if entities:
            for ent in entities:
                if ent.get('id') != entity_id:
                    return True

        return False

    def add(self, ex):
        if not self.url_cache.get(ex.url):
            self.url_cache[ex.url] = []

        if not self.entity_cache.get(ex.id):
            self.entity_cache[ex.id] = []

        self.url_cache[ex.url].append({'id':ex.entity_id})
        self.entity_cache[ex.id].append({'url':ex.url})



    # def get_deletions(self, url, entity_id):
    #     deletions = []
    #     entities = self.url_cache.get(url)
    #     if entities:
    #         for ent in entities:
    #             if ent.entity_id == entity_id:
    #                 deletions.append(ent.id)
    #     return deletions


class IpdProcedureSeo:

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
        self.create_search_urls()
        # self.create_doctor_page_urls()
        # self.update_breadcrumbs()
        self.insert_search_urls()

    def insert_search_urls(self):
        seq = self.sequence

        query = '''insert into entity_urls(sequence,extras, sitemap_identifier, url, count, entity_type, 
                 url_type,  created_at, 
                 updated_at,  sublocality_latitude, sublocality_longitude, locality_latitude, 
                 locality_longitude, locality_id, sublocality_id,
                 locality_value, sublocality_value, is_valid, locality_location, sublocality_location, location, entity_id, 
                 specialization_id, specialization, breadcrumb, ipd_procedure_id, ipd_procedure)

                 select %d as sequence ,a.extras, a.sitemap_identifier, getslug(a.url) as a_url, a.count, a.entity_type,
                  a.url_type, now() as created_at, now() as updated_at,
                  a.sublocality_latitude, a.sublocality_longitude, a.locality_latitude, a.locality_longitude,
                  a.locality_id, a.sublocality_id, a.locality_value, a.sublocality_value, a.is_valid, 
                  a.locality_location, a.sublocality_location, a.location, entity_id, 
                  specialization_id, specialization, breadcrumb, a.ipd_procedure_id, a.ipd_procedure from temp_url a
                  ''' % seq

        update_query = '''update entity_urls set is_valid=false where sitemap_identifier 
                           in ('IPD_PROCEDURE_CITY', 'IPD_PROCEDURE_HOSPITAL_CITY', 
                           'IPD_PROCEDURE_DOCTOR_CITY') and sequence< %d''' % seq

        cleanup = '''delete from entity_urls where id in (select id from 
        (select eu.*, row_number() over(partition by url order by is_valid desc, sequence desc) rownum from entity_urls eu  
        )x where rownum>1
        ) '''

        RawSql(query, []).execute()
        RawSql(update_query, []).execute()
        RawSql(cleanup, []).execute()

        return True

    def create_search_urls(self):

        q2 = '''insert into temp_url (ipd_procedure_id, ipd_procedure, search_slug, locality_id, 
                      sitemap_identifier, entity_type, url_type, is_valid, created_at, updated_at )
                    select ipdp.id, ipdp.name, search_slug,
                    case when ea.type = 'LOCALITY' then ea.id end as locality_id,
                    case when ea.type = 'LOCALITY' then 'IPD_PROCEDURE_CITY' end as sitemap_identifier,
                    'IpdProcedure' as entity_type, 'PAGEURL' url_type, True as is_valid, now(), now()
                    from entity_address ea 
                    inner join hospital h on (ea.type = 'LOCALITY' and 
                    ST_DWithin(ea.centroid::geography,h.location::geography,15000)) and h.is_live=true
                    and ea.type IN ('LOCALITY') and ea.use_in_url=true
                    inner join doctor_clinic dc on dc.hospital_id = h.id and dc.enabled=true 
                    inner join doctor_clinic_ipd_procedure dcip on dcip.doctor_clinic_id = dc.id
                    inner join ipd_procedure ipdp on ipdp.id = dcip.ipd_procedure_id and ipdp.is_enabled=True
                    inner join doctor d on dc.doctor_id= d.id and d.is_live=true
                    where ea.id>=%d and ea.id<%d
                    group by ea.id, ipdp.id'''

        start = self.min_ea
        while start < self.max_ea:
            # query = q1 % (start, start + self.step)
            # RawSql(query, []).execute()
            query = q2 % (start, start + self.step)
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
        RawSql('''update temp_url set location = locality_location where location is null''', []).execute()

        update_spec_extras_query = '''update  temp_url 
                                  set extras = 
                                   json_build_object('ipd_procedure_id', ipd_procedure_id, 'location_json',
                                   json_build_object('locality_id', locality_id, 'locality_value', locality_value, 'locality_latitude', 
                                   locality_latitude,'locality_longitude', locality_longitude), 'ipd_procedure', ipd_procedure)
                                  where sitemap_identifier in ('IPD_PROCEDURE_CITY')'''
        RawSql(update_spec_extras_query, []).execute()

        copy_for_hospitals = '''insert into temp_url (ipd_procedure_id, ipd_procedure, search_slug, locality_id, 
                      sitemap_identifier, entity_type, url_type, is_valid, created_at, updated_at, 
                      locality_latitude, locality_longitude, locality_value, locality_location, location, extras) 
            select ipd_procedure_id, ipd_procedure, search_slug, locality_id, 
                      'IPD_PROCEDURE_HOSPITAL_CITY' as sitemap_identifier, 'Hospital', 'SEARCHURL' as url_type, is_valid, 
                      now(), now(), locality_latitude, locality_longitude, locality_value
                      , locality_location, location, extras from temp_url where sitemap_identifier = 'IPD_PROCEDURE_CITY' '''
        RawSql(copy_for_hospitals, []).execute()

        copy_for_doctors = '''insert into temp_url (ipd_procedure_id, ipd_procedure, search_slug, locality_id, 
                              sitemap_identifier, entity_type, url_type, is_valid, created_at, updated_at, 
                              locality_latitude, locality_longitude, locality_value, locality_location, location, extras) 
                    select ipd_procedure_id, ipd_procedure, search_slug, locality_id, 
                                  'IPD_PROCEDURE_DOCTOR_CITY' as sitemap_identifier, 'Doctor', 'SEARCHURL' as url_type, is_valid, 
                              now(), now(), locality_latitude, locality_longitude, locality_value
                              , locality_location, location, extras from temp_url where sitemap_identifier = 'IPD_PROCEDURE_CITY' '''
        RawSql(copy_for_doctors, []).execute()

        # IPD_PROCEDURE_COST_IN_IPDP
        update_urls_query = '''update temp_url set url =  
                    slugify_url(concat(ipd_procedure,'-cost-in-', search_slug, '-ipdp'))
                    where sitemap_identifier in ('IPD_PROCEDURE_CITY')'''
        RawSql(update_urls_query, []).execute()

        # IPD_PROCEDURE_HOSPITAL_CITY_IPDHP
        update_urls_query_2 = '''update temp_url set url =  
                            slugify_url(concat(ipd_procedure,'-hospitals-in-', search_slug, '-ipdhp'))
                            where sitemap_identifier in ('IPD_PROCEDURE_HOSPITAL_CITY')'''
        RawSql(update_urls_query_2, []).execute()

        # IPD_PROCEDURE_DOCTOR_CITY_IPDDP
        update_urls_query_3 = '''update temp_url set url =  
                                    slugify_url(concat(ipd_procedure,'-doctors-in-', search_slug, '-ipddp'))
                                    where sitemap_identifier in ('IPD_PROCEDURE_DOCTOR_CITY')'''
        RawSql(update_urls_query_3, []).execute()


        RawSql('''delete from temp_url where id in (select id from (select tu.*,
                row_number() over(partition by tu.url order by ea.child_count desc nulls last, tu.count desc nulls last) rownum
                from temp_url tu inner join entity_address ea on 
                case when tu.sublocality_id is not null then tu.sublocality_id else tu.locality_id end = ea.id 
                )x where rownum>1)
                ''', []).execute()

        return 'success'




