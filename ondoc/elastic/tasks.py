from __future__ import absolute_import, unicode_literals
from django.core.files.uploadedfile import InMemoryUploadedFile

from celery import task
import logging
import datetime
import json
from ondoc.api.v1.utils import RawSql
from io import StringIO, BytesIO
from ondoc.elastic import models as elastic_models
logger = logging.getLogger(__name__)
from django.template.defaultfilters import slugify
from django.core.files.storage import default_storage


@task(bind=True, max_retries=2)
def fetch_and_upload_json(self, data):
    try:
        obj_id = data.get('id', None)
        obj = elastic_models.DemoElastic.objects.filter(id=obj_id).first()
        if obj:
            query = '''select * from
            (
                select
                concat(doctor_name,
                ' ',
                gender,
                ' ',
                replace(replace(trim(expspecializations, '"'),'", "',' '),'null',' '),
                ' ',
                replace(replace(trim(expqualifications, '"'),'", "',' '),'null',' '),
                ' ',
                replace(replace(trim(exphosptialname, '"'),'", "',' '),'null',' ')
                ) as meta_data,
                'doctor' as type,
                doctor_id,
                replace(replace(replace(doctor_name,'"',''),'[',''),']','') as doctor_name,
                gender,
                practicing_since,
                is_internal,
                enabled,
                enabled_for_online_booking,
                is_license_verified,
                is_gold,
                source,
                qualifications::text,
                doctor_image_id,
                doctor_image_path,
                doc_calender::text,
                hospitals::text,
                specializations::text,
                specialization_ids::text,
                specializations_with_id::text,
                popularity,
                popularity_score,
                rating_percent,
                votes_count,
                reviews_count,
                is_live,
                is_insurance_enabled,
                is_retail_enabled,
                    cast(null as int) lab_id,
                    cast(null as text) lab_name,
                    cast(null as int) as lab_pricing_group_id,
                    cast(null as bool) always_open,
                    cast(null as int) operational_since,
                    cast(null as int) parking,
                    cast(null as int) network_id,
                    cast(null as int) network_type,
                    cast(null as text) "location",
                    cast(null as text) building,
                    cast(null as text) sublocality,
                    cast(null as text) locality,
                    cast(null as text) city,
                    cast(null as text) state,
                    cast(null as text) country,
                    cast(null as int) pin_code,
                    cast(null as int) home_pickup_charges,
                    cast(null as bool) is_home_collection_enabled,
                    cast(null as bool) is_ppc_pathology_enabled,
                    cast(null as bool) is_ppc_radiology_enabled,
                    cast(null as bool) is_billing_enabled,
                    cast(null as bool) lab_enabled,
                    cast(null as int) test_id,
                    cast(null as int) available_lab_test_id,
                    cast(null as text) test_name,
                    cast(null as text) test_preferred_time,
                    cast(null as bool) test_is_package,
                    cast(null as bool) test_home_collection_possible,
                    cast(null as int) test_mrp,
                    cast(null as int) test_computed_agreed_price,
                    cast(null as int) test_computed_deal_price,
                    cast(null as bool) test_enabled,
                    cast(null as text) lab_calender,
                    cast(null as text) doctor_availability
                from(
                select
                trim(b.hospitals_name::text, '[,]') as exphosptialname,
                trim(specializations::text, '[,]') as expspecializations,
                trim(qualifications::text, '[,]') as expqualifications,
                a.id as doctor_id,
                b.doctor_name,
                replace(replace(a.gender,'m','male'),'f','female') as gender,
                a.practicing_since,
                a.is_live::bool,
                a.is_internal,
                a.enabled,
                a.enabled_for_online_booking,
                a.is_license_verified,
                a.is_insurance_enabled,
                a.is_gold,
                a.is_retail_enabled,
                a.source,
                e.qualifications,
                e.doctor_image_id,
                e.doctor_image_path,
                a.doc_calender,
                b.hospitals,
                c.specializations,
                c.specialization_ids,
                c.specializations_with_id,
                f.popularity,
                f.popularity_score,
                f.rating_percent,
                f.votes_count,
                f.reviews_count
                from
                (
                select d.id, d.name as doctor_name,
                d.gender,d.practicing_since,d.is_live,
                d.is_internal,d.enabled,d.enabled_for_online_booking,
                d.is_license_verified,d.is_insurance_enabled,
                d.is_gold,d.is_retail_enabled,d.source,
                json_agg(doc_calender) as doc_calender
                from doctor d
                left join (
                    select dc.doctor_id,
                    json_build_object('day',dct.day,
                    'timings',json_agg(
                    json_build_object('start_time', dct."start",
                    'end_time', dct."end", 'fees', dct.fees,'mrp',dct.mrp,
                    'deal_price',dct.deal_price,
                    'hospital',
                    json_build_object('hospital_id', h.id,
                    'hospital_name',
                    replace(replace(replace(h."name",'"',''),'[',''),']',''),
                    'city', h.city,
                    'sublocality',
                    replace(replace(replace(h.sublocality,'"',''),'[',''),']',''),
                    'location',concat_ws(',',ST_Y(location::geometry),ST_X(location::geometry)),
                    'state', h.state)
                    ))) as doc_calender
                    from doctor_clinic_timing dct
                    left join doctor_clinic dc on dc.id=dct.doctor_clinic_id
                    left join hospital h on h.id=dc.hospital_id
                    group by dc.doctor_id,dct.day
                    ) b
                    on d.id = b.doctor_id
                    where d.practicing_since is not null
                    group by d.id
                    ) a
                left join
                    (select d.id, d.name as doctor_name,
                    json_agg(json_build_object('hospital_id', h.id,
                    'hospital_name',
                    replace(replace(replace(h."name",'"',''),'[',''),']',''),
                    'city', h.city,'sublocality',
                    replace(replace(replace(h.sublocality,'"',''),'[',''),']',''),
                    'location',concat_ws(',',ST_Y(location::geometry),ST_X(location::geometry)),
                    'state', h.state)) as hospitals,
                    json_agg(concat(
                    replace(replace(replace(h."name",'"',''),'[',''),']',''),
                    ' ',
                    replace(replace(replace(h.sublocality,'"',''),'[',''),']',''),
                    ' ',
                    h.city,' ',h.state)) as hospitals_name
                    from doctor d
                    left join doctor_clinic dc on dc.doctor_id = d.id
                    left join hospital h on h.id=dc.hospital_id
                    group by d.id) b on a.id = b.id
                left join
                    (select d.id, d.name as doctor_name,json_agg((gs.name)) as specializations,
                    json_agg((gs.id)) as specialization_ids,
                    json_agg(json_build_object('specialization_id',gs.id,'specialization_name',gs.name)) as specializations_with_id
                    from doctor d
                    left join doctor_practice_specialization ds on ds.doctor_id = d.id
                    left join practice_specialization gs on gs.id = ds.specialization_id
                    group by d.id) c on a.id = c.id
                left join
                    (
                        select json_agg((q.name)) as qualifications,
                        dq.doctor_id, di.name as doctor_image_path,
                        di.id as doctor_image_id
                        from doctor_qualification dq
                        left join qualification q on dq.qualification_id = q.id
                        left join doctor_image di on di.id = dq.doctor_id
                        where q.name is not null and
                        di.name is not null and
                        di.id is not null
                        group by dq.doctor_id,di.name,di.id
                    ) e on e.doctor_id = c.id
                left join
                    (select distinct doctor_id, dp.unique_identifier,
                    popularity,popularity_score,rating_percent,votes_count,
                    reviews_count
                    from (select doctor_id,split_part(processed_url,'/',4) as unique_identifier
                    from competitor_info) ci
                    inner join
                    doctor_popularity dp on
                    ci.unique_identifier = dp.unique_identifier)
                    f on f.doctor_id = c.id
                ) y

            ) a
            union
            (
                    select
                    concat(
                    lab_name,
                    ' ',
                    test_name,
                    ' ',
                    building,
                    ' ',
                    sublocality,
                    ' ',
                    locality,
                    ' ',
                    city,
                    ' ',
                    state
                    ) as meta_data,
                    'lab_test' as type,
                    cast(null as int) doctor_id,
                cast(null as text) doctor_name,
                cast(null as text) gender,
                cast(null as int) practicing_since,
                cast(null as bool) is_internal,
                cast(null as bool) enabled,
                cast(null as bool) enabled_for_online_booking,
                cast(null as bool) is_license_verified,
                cast(null as bool) is_gold,
                cast(null as text) source,
                cast(null as text) qualifications,
                cast(null as int) doctor_image_id,
                cast(null as text) doctor_image_path,
                cast(null as text) doc_calender,
                cast(null as text) hospitals,
                cast(null as text) specializations,
                cast(null as text) specialization_ids,
                cast(null as text) specializations_with_id,
                cast(null as int) popularity,
                cast(null as int) popularity_score,
                cast(null as int) rating_percent,
                cast(null as int) votes_count,
                cast(null as int) reviews_count,
                is_live,
                is_insurance_enabled,
                is_retail_enabled,
                    la_id as lab_id,
                    lab_name,
                    lab_pricing_group_id,
                    always_open,
                    operational_since,
                    parking,
                    network_id,
                    network_type,
                    location,
                    building,
                    sublocality,
                    locality,
                    city,
                    state,
                    country,
                    pin_code,
                    home_pickup_charges,
                    is_home_collection_enabled,
                    is_ppc_pathology_enabled,
                    is_ppc_radiology_enabled,
                    is_billing_enabled,
                    lab_enabled,
                    test_id,
                    available_lab_test_id,
                    test_name,
                    test_preferred_time,
                    test_is_package,
                    test_home_collection_possible,
                    test_mrp,
                    test_computed_agreed_price,
                    test_computed_deal_price,
                    test_enabled,
                    lab_calender::text,
                    doctor_availability::text
                    from (
                    select
                    l.id as la_id,
                    replace(replace(replace(l.name,'"',''),'[',''),']','') as lab_name,
                    l.is_live::bool,
                    l.lab_pricing_group_id,
                    l.always_open,
                    l.operational_since,
                    l.parking,
                    l.network_id,
                    l.network_type,
                    concat_ws(',',ST_Y(l.location::geometry),ST_X(l.location::geometry)) as location,
                    replace(replace(replace(l.building,'"',''),'[',''),']','') as building,
                    replace(replace(replace(l.sublocality,'"',''),'[',''),']','') as sublocality,
                    replace(replace(replace(l.locality,'"',''),'[',''),']','') as locality,
                    replace(replace(replace(l.city,'"',''),'[',''),']','') as city,
                    replace(replace(replace(l.state,'"',''),'[',''),']','') as state,
                    l.country,
                    l.pin_code,
                    l.home_pickup_charges,
                    l.is_home_collection_enabled,
                    l.is_insurance_enabled,
                    l.is_retail_enabled,
                    l.is_ppc_pathology_enabled,
                    l.is_ppc_radiology_enabled,
                    l.is_billing_enabled,
                    l.enabled as lab_enabled,
                    lt.id as test_id,
                    alt.id as available_lab_test_id,
                    replace(replace(replace(lt.name,'"',''),'[',''),']','') as test_name,
                    lt.preferred_time as test_preferred_time,
                    lt.is_package as test_is_package,
                    lt.home_collection_possible as test_home_collection_possible,
                    alt.mrp as test_mrp,
                    alt.computed_agreed_price as test_computed_agreed_price,
                    alt.computed_deal_price as test_computed_deal_price,
                    alt.enabled as test_enabled
                    from lab l
                    left join available_lab_test alt
                    on alt.lab_pricing_group_id = l.lab_pricing_group_id
                    left join lab_test lt on alt.test_id = lt.id where l.is_live = true and l.lab_pricing_group_id is not null and alt.test_id is not null
                    group by l.id,lt.id,alt.id) a
                    left join
                    (select
                    lab_id,
                    lab_calender,
                    doctor_availability
                    from
                                (select lab_id as l_id,json_agg(json_build_object(
                                'slot',slot,
                                'is_male_available',is_male_available,
                                'is_female_available',is_female_available))
                                as doctor_availability
                                from lab_doctor_availability
                                group by lab_id) b
                    left join
                            (select lab_id,json_agg(lab_calender) as lab_calender from
                                (select lab_id,
                                json_build_object(
                                'day',day,
                                'timings',
                                json_agg(
                                json_build_object(
                                'start',start,'end',"end",
                                'for_home_pickup',for_home_pickup
                                ))
                                ) as lab_calender
                                from lab_timing
                                group by day,lab_id) r group by r.lab_id
                            )c
                    on b.l_id = c.lab_id) x
                    on x.lab_id = a.la_id
            )'''

            results = RawSql(query).fetch_lazily(10000)

            response_list = list()
            new_file_name = str(slugify('%s' % str(obj.created_at)))
            new_file_name = '%s.json' % new_file_name
            file = default_storage.open('demoelastic/%s' % new_file_name, 'w')
            file.write('[')
            for sql_rows in results:
                for result in sql_rows:
                    dic = dict()
                    for k, v in result.items():
                        try:
                            json.dumps(v)
                        except TypeError:
                            v = str(v)
                        dic[k] = v

                    response_list.append(dic)

                content = json.dumps(response_list)
                file.write(content[1:len(content)-1])
                file.write(',')

            file.write('{}')
            file.write(']')
            file.close()

            obj.path = file.name
            obj.save()


    except Exception as e:
        logger.error("Error in Celery. Failed creating json and uploading S3 - " + str(e))
