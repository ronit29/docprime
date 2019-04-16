from django.db.models import Prefetch
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
        self.create_hosp_search_urls()
        self.create_hospital_page_urls()
        self.update_breadcrumbs()
        self.insert_search_urls()

    def insert_search_urls(self):

        seq = self.sequence

        query = '''insert into entity_urls(sequence,extras, sitemap_identifier, url, count, entity_type, 
                 url_type,  created_at, 
                 updated_at,  sublocality_latitude, sublocality_longitude, locality_latitude, 
                 locality_longitude, locality_id, sublocality_id,
                 locality_value, sublocality_value, is_valid, locality_location, sublocality_location, location, entity_id, 
                 specialization_id, specialization, breadcrumb)

                 select %d as sequence ,a.extras, a.sitemap_identifier,getslug(a.url) as url, a.count, a.entity_type,
                  a.url_type, now() as created_at, now() as updated_at,
                  a.sublocality_latitude, a.sublocality_longitude, a.locality_latitude, a.locality_longitude,
                  a.locality_id, a.sublocality_id, a.locality_value, a.sublocality_value, a.is_valid, 
                  a.locality_location, a.sublocality_location, a.location, entity_id, 
                  specialization_id, specialization, breadcrumb from temp_url a
                  ''' % seq

        update_query = '''update entity_urls set is_valid=false where sitemap_identifier 
                           in ('HOSPITALS_LOCALITY_CITY', 'HOSPITALS_CITY', 'HOSPITAL_PAGE') and sequence< %d''' % seq

        cleanup = '''delete from entity_urls where id in (select id from 
        (select eu.*, row_number() over(partition by url order by is_valid desc, sequence desc) rownum from entity_urls eu  
        )x where rownum>1
        ) '''

        RawSql(query, []).execute()
        RawSql(update_query, []).execute()
        RawSql(cleanup, []).execute()

        return True

    def create_hosp_search_urls(self):

        q1 = '''insert into temp_url (search_slug, count, sublocality_id, locality_id, 
                      sitemap_identifier, entity_type, url_type, is_valid, created_at, updated_at )
                    select search_slug, count(distinct d.id) count,
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
                    group by ea.id '''

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

        RawSql('''update temp_url tu set breadcrumb=(select json_build_array(json_build_object('title', locality_value, 'url', url, 'link_title', concat('Hospitals in ',locality_value))) 
                   from temp_url where sitemap_identifier ='HOSPITALS_CITY' and lower(locality_value)=lower(tu.locality_value)
                   and st_dwithin(location::geography, tu.location::geography, 20000) order by st_distance(location, tu.location) asc limit 1)
                   where sitemap_identifier ='HOSPITALS_LOCALITY_CITY' ''', []).execute()

        # update for hospital profile from city if null
        RawSql('''update temp_url  tu set breadcrumb = (select breadcrumb from temp_url where
                sitemap_identifier = 'HOSPITALS_LOCALITY_CITY' and lower(locality_value)=lower(tu.locality_value) and
                st_dwithin(location::geography, tu.location::geography, 20000) order by st_distance(location, tu.location) asc
                limit 1) where sitemap_identifier = 'HOSPITAL_PAGE' ''', []).execute()

        RawSql('''update temp_url tu set breadcrumb=json_build_array() where breadcrumb is null ''', []).execute()

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

        hosp_obj = hosp_obj.annotate(doctors_count=Count('assoc_doctors'))


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
