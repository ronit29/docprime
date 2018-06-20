from ondoc.doctor import models
from ondoc.authentication import models as auth_models
from ondoc.account import models as account_models
from . import serializers
from ondoc.api.v1.diagnostic.views import TimeSlotExtraction
from ondoc.api.pagination import paginate_queryset, paginate_raw_query
from ondoc.api.v1.utils import convert_timings, form_time_slot
from django.db.models import Min
from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework import mixins
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db import transaction
from django.http import Http404
from django.db.models import Q
import datetime
from operator import itemgetter
from itertools import groupby
from ondoc.api.v1.utils import RawSql
from django.contrib.auth import get_user_model
from django.db.models import F
from collections import defaultdict

User = get_user_model()


class CreateAppointmentPermission(permissions.BasePermission):
    message = 'creating appointment is not allowed.'

    def has_permission(self, request, view):
        if request.user.user_type==User.CONSUMER:
            return True
        return False


class DoctorPermission(permissions.BasePermission):
    message = 'Doctor is allowed to perform action only.'

    def has_permission(self, request, view):
        if request.user.user_type == User.DOCTOR:
            return True
        return False


class OndocViewSet(mixins.CreateModelMixin,
                   mixins.RetrieveModelMixin,
                   mixins.UpdateModelMixin,
                   mixins.ListModelMixin,
                   viewsets.GenericViewSet):
    pass


class DoctorAppointmentsViewSet(OndocViewSet):
#     filter_backends = (DjangoFilterBackend)
    permission_classes = (IsAuthenticated,)
#     #queryset = OpdAppointment.objects.all()
    serializer_class = serializers.OpdAppointmentSerializer
#     filter_fields = ('hospital','profile','')

#     # def list (self, request):
#     #     return super().list()

#     def get_queryset(self):

#         user = self.request.user
#         if user.user_type== User.DOCTOR:
#             return OpdAppointment.objects.all(doctor=user.doctor)
#         elif user.user_type== User.CONSUMER:
#             return OpdAppointment.objects.all(user=user)

    def get_queryset(self):

        user = self.request.user
        if user.user_type == User.DOCTOR:
            return models.OpdAppointment.objects.filter(doctor=user.doctor)
        elif user.user_type == User.CONSUMER:
            return models.OpdAppointment.objects.filter(user=user)
    # queryset = auth_models.UserPermission.objects.all()

    def list(self, request):

        user_permission = (auth_models.UserPermission.objects.
                           filter(user=request.user, doctor__appointments__hospital=F('hospital'),
                                  doctor__appointments__doctor=F('doctor')).
                           prefetch_related('doctor__appointments', 'doctor', 'hospital', 'user').
                           values('permission_type', 'read_permission', 'write_permission', 'delete_permission',
                                  'doctor__appointments__id'))

        ids, id_dict = self.extract_appointment_ids(user_permission)

        queryset = models.OpdAppointment.objects.filter(id__in=ids)

        if not queryset:
            return Response([])
        serializer = serializers.AppointmentFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        range = serializer.validated_data.get('range')
        hospital_id = serializer.validated_data.get('hospital_id')
        profile_id = serializer.validated_data.get('profile_id')

        if profile_id:
            queryset = queryset.filter(profile=profile_id)

        if hospital_id:
            queryset = queryset.filter(hospital_id=hospital_id)

        if range=='previous':
            queryset = queryset.filter(status__in = [models.OpdAppointment.COMPLETED,models.OpdAppointment.CANCELED]).order_by('-time_slot_start')
        elif range=='upcoming':
            today = datetime.date.today()
            queryset = queryset.filter(
                status__in=[models.OpdAppointment.CREATED, models.OpdAppointment.RESCHEDULED_PATIENT,
                            models.OpdAppointment.RESCHEDULED_DOCTOR, models.OpdAppointment.ACCEPTED],
                time_slot_start__date__gte=today).order_by('time_slot_start')
        elif range =='pending':
            queryset = queryset.filter(time_slot_start__gt=timezone.now(), status__in = [models.OpdAppointment.BOOKED,
                                                                                         models.OpdAppointment.RESCHEDULED_PATIENT
                                                                                         ]).order_by('time_slot_start')
        else:
            queryset = queryset.order_by('-time_slot_start')

        queryset = paginate_queryset(queryset, request)
        whole_queryset = self.extract_whole_queryset(queryset, id_dict)
        serializer = serializers.OpdAppointmentSerializer(queryset, many=True, context={'request':request})
        # serializer = serializers.OpdAppointmentPermissionSerializer(whole_queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        user = request.user
        queryset = models.OpdAppointment.objects.filter(pk=pk).filter(doctor=user.doctor)
        if queryset:
            serializer = serializers.AppointmentRetrieveSerializer(queryset, many=True, context={'request':request})
            return Response(serializer.data)
        else:
            return Response([])

    def payment_retry(self, request, pk=None):
        queryset = models.OpdAppointment.objects.filter(pk=pk)
        payment_response = dict()
        if queryset:
            serializer_data = serializers.OpdAppointmentSerializer(queryset.first(), context={'request':request})
            payment_response = self.extract_payment_details(request, serializer_data.data, 1)
        return Response(payment_response)

    def complete(self, request):
        serializer = serializers.OTPFieldSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        opd_appointment = get_object_or_404(models.OpdAppointment, pk=validated_data.get('id'))
        permission_queryset = (auth_models.UserPermission.objects.filter(doctor=opd_appointment.doctor.id).
                               filter(hospital=opd_appointment.hospital_id))
        if permission_queryset:
            perm_data = permission_queryset.first()
            if request.user.user_type == User.DOCTOR and perm_data.write_permission:
                otp_valid_serializer = serializers.OTPConfirmationSerializer(data=request.data)
                otp_valid_serializer.is_valid(raise_exception=True)
                updated_opd_appointment = opd_appointment.action_completed(opd_appointment)
        opd_appointment_serializer = serializers.OpdAppointmentSerializer(updated_opd_appointment, context={'request': request})
        return Response(opd_appointment_serializer.data)

    @transaction.atomic
    def create(self, request):
        serializer = serializers.CreateAppointmentSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        time_slot_start = form_time_slot(data.get("start_date"), data.get("start_time"))
        doctor_hospital = models.DoctorHospital.objects.filter(
            doctor=data.get('doctor'), hospital=data.get('hospital'),
            day=time_slot_start.weekday(), start__lte=time_slot_start.hour,
            end__gte=time_slot_start.hour).first()
        profile_model = data.get("profile")
        profile_detail = {
            "name": profile_model.name,
            "gender": profile_model.gender,
            "dob": str(profile_model.dob)
        }
        opd_data = {
            "doctor": data.get("doctor").id,
            "hospital": data.get("hospital").id,
            "profile": data.get("profile").id,
            "profile_detail": profile_detail,
            "user": request.user.id,
            "booked_by": request.user.id,
            "fees": doctor_hospital.fees,
            "discounted_price": doctor_hospital.discounted_price,
            "effective_price": doctor_hospital.discounted_price,
            "mrp": doctor_hospital.mrp,
            "time_slot_start": str(time_slot_start),
        }
        resp = self.extract_payment_details(request, opd_data, 1)
        return Response(data=resp)

    def update(self, request, pk=None):
        opd_appointment = get_object_or_404(models.OpdAppointment, pk=pk)
        serializer = serializers.UpdateStatusSerializer(data=request.data,
                                            context={'request': request, 'opd_appointment': opd_appointment})
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        allowed = opd_appointment.allowed_action(request.user.user_type)
        appt_status = validated_data['status']
        if appt_status not in allowed:
            resp = {}
            resp['allowed'] = allowed
            return Response(resp, status=status.HTTP_400_BAD_REQUEST)

        if request.user.user_type == User.DOCTOR:
            req_status = validated_data.get('status')
            if req_status == models.OpdAppointment.RESCHEDULED_DOCTOR:
                updated_opd_appointment = opd_appointment.action_rescheduled_doctor(opd_appointment)
            elif req_status == models.OpdAppointment.ACCEPTED:
                updated_opd_appointment = opd_appointment.action_accepted(opd_appointment)

        opd_appointment_serializer = serializers.OpdAppointmentSerializer(updated_opd_appointment, context={'request':request})
        response = {
            "status": 1,
            "data": opd_appointment_serializer.data
        }
        return Response(response)

    # def doctor_update(self, opd_appointment, validated_data):
    #     opd_appointment.status = validated_data.get('status')
    #     opd_appointment.save()
    #     return opd_appointment

    # def consumer_update(self, opd_appointment, validated_data):
    #     opd_appointment.status = validated_data.get('status')
    #     if validated_data.get('status') == models.OpdAppointment.RESCHEDULED_PATIENT:
    #         opd_appointment.time_slot_start = validated_data.get("time_slot_start")
    #         opd_appointment.time_slot_end = validated_data.get("time_slot_end")
    #     opd_appointment.save()
    #     return opd_appointment

    def extract_appointment_ids(self, appointment_data):
        id_dict = defaultdict(dict)
        id_list = list()
        for data in appointment_data:
            temp = dict()
            temp["appointment"] = data['doctor__appointments__id']
            temp["permission_type"] = data['permission_type']
            temp["read_permission"] = data['read_permission']
            temp["write_permission"] = data['write_permission']
            temp["delete_permission"] = data['delete_permission']
            # temp["permission"] = data['permission']
            id_dict[data['doctor__appointments__id']] = temp
            id_list.append(data['doctor__appointments__id'])
        return id_list, id_dict

    def extract_whole_queryset(self, queryset, id_dict):
        whole_queryset = list()
        for data in queryset:
            temp = id_dict[data.id]
            temp['appointment'] = data
            whole_queryset.append(temp)
        return whole_queryset

    @transaction.atomic
    def extract_payment_details(self, request, appointment_details, product_id):
        remaining_amount = 0
        user = request.user
        consumer_account = account_models.ConsumerAccount.objects.get_or_create(user=user)
        consumer_account = account_models.ConsumerAccount.objects.select_for_update().get(user=user)
        balance = consumer_account.balance
        resp = {}
        opd_seriailizer = serializers.OpdAppointmentSerializer(data=appointment_details, context={"request": request})
        opd_seriailizer.is_valid(raise_exception=True)
        if balance >= appointment_details.get("effective_price"):
            opd_seriailizer.save()
            user_account_data = {
                "user": user,
                "product_id": product_id,
                "reference_id": opd_seriailizer.data.get("id")
            }
            consumer_account.debit_schedule(user_account_data, appointment_details.get("effective_price"))
            resp["status"] = 1
            resp["data"] = opd_seriailizer.data
        else:
            account_models.Order.objects.filter(
                action_data__doctor=appointment_details.get("doctor"),
                action_data__hospital=appointment_details.get("hospital"),
                action_data__profile=appointment_details.get("profile"),
                action_data__user=appointment_details.get("user"),
                product_id=product_id,
                is_viewable=True,
                payment_status=account_models.Order.PAYMENT_PENDING,
                action=account_models.Order.OPD_APPOINTMENT_CREATE,
            ).update(is_viewable=False)
            order = account_models.Order.objects.create(
                product_id=product_id,
                action=account_models.Order.OPD_APPOINTMENT_CREATE,
                action_data=appointment_details,
                amount=appointment_details.get("effective_price") - consumer_account.balance,
                payment_status=account_models.Order.PAYMENT_PENDING
            )
            appointment_details["payable_amount"] = appointment_details.get("effective_price") - balance
            resp["status"] = 1
            resp['pg_details'] = self.payment_details(request, appointment_details, product_id, order.id)
        return resp

    def payment_details(self, request, appointment_details, product_id, order_id):
        details = dict()
        pgdata = dict()
        if appointment_details["payable_amount"] != 0:
            user = request.user
            user_profile = user.profiles.filter(is_default_user=True).first()
            pgdata['custId'] = user.id
            pgdata['mobile'] = user.phone_number
            pgdata['email'] = user.email
            if not user.email:
                pgdata['email'] = "dummy_appointment@policybazaar.com"

            pgdata['productId'] = product_id
            base_url = (
                "https://{}".format(request.get_host()) if request.is_secure() else "http://{}".format(request.get_host()))
            pgdata['surl'] = base_url + '/api/v1/user/transaction/save'
            pgdata['furl'] = base_url + '/api/v1/user/transaction/save'
            pgdata['checkSum'] = ''
            pgdata['referenceId'] = ""
            pgdata['orderId'] = order_id
            if user_profile:
                pgdata['name'] = user_profile.name
            else:
                pgdata['name'] = "DummyName"
            pgdata['txAmount'] = appointment_details['payable_amount']

        if pgdata:
            details['required'] = True
            details['pgdata'] = pgdata
        else:
            details['required'] = False

        return details


class DoctorProfileView(viewsets.GenericViewSet):
    permission_classes = (IsAuthenticated,)

    def retrieve(self, request):
        doctor = get_object_or_404(models.Doctor, pk=request.user.doctor.id)
        serializer = serializers.DoctorProfileSerializer(doctor, many=False,
                                                         context={"request": request})

        now = datetime.datetime.now()
        appointment_count = models.OpdAppointment.objects.filter(Q(doctor=request.user.doctor.id),
                                                                 ~Q(status=models.OpdAppointment.CANCELED),
                                                                 Q(time_slot_start__gte=now)).count()
        hospital_queryset = doctor.hospitals.distinct()
        hospital_serializer = serializers.HospitalModelSerializer(hospital_queryset, many=True)

        temp_data = serializer.data
        temp_data["count"] = appointment_count
        temp_data['hospitals'] = hospital_serializer.data
        return Response(temp_data)


class DoctorProfileUserViewSet(viewsets.GenericViewSet):

    def prepare_response(self, response_data):
        hospitals = sorted(response_data.get('hospitals'), key=itemgetter("hospital_id"))
        availability = []
        for key, group in groupby(hospitals, lambda x: x['hospital_id']):
            hospital_groups = list(group)
            hospital = hospital_groups[0]
            timings = convert_timings(hospital_groups)
            hospital.update({
                "timings": timings
            })
            hospital.pop("start", None)
            hospital.pop("end", None)
            hospital.pop("day",  None)
            availability.append(hospital)
        response_data['hospitals'] = availability
        return response_data

    def retrieve(self, request, pk):
        doctor = (models.Doctor.objects
                  .prefetch_related('languages__language',
                                    'availability__hospital',
                                    'qualifications__qualification',
                                    'qualifications__specialization',
                                    )
                  .filter(pk=pk).first())
        if not doctor:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        serializer = serializers.DoctorProfileUserViewSerializer(doctor, many=False,
                                                                 context={"request": request})
        response_data = self.prepare_response(serializer.data)
        return Response(response_data)


class DoctorHospitalView(mixins.ListModelMixin,
                         mixins.RetrieveModelMixin,
                         viewsets.GenericViewSet):

    permission_classes = (IsAuthenticated,)

    queryset = models.DoctorHospital.objects.all()
    serializer_class = serializers.DoctorHospitalSerializer

    def get_queryset(self):
        user = self.request.user
        if user.user_type == User.DOCTOR:
            return models.DoctorHospital.objects.filter(doctor=user.doctor)

    def list(self, request):
        user = request.user
        queryset = self.get_queryset().values('hospital').annotate(min_fees=Min('fees'))

        serializer = serializers.DoctorHospitalListSerializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk):
        user = request.user

        queryset = self.get_queryset().filter(hospital=pk)
        if len(queryset) == 0:
            raise Http404("No Hospital matches the given query.")

        schedule_serializer = serializers.DoctorHospitalScheduleSerializer(queryset, many=True)
        hospital_queryset = queryset.first().hospital
        hospital_serializer = serializers.HospitalModelSerializer(hospital_queryset)

        temp_data = dict()
        temp_data['hospital'] = hospital_serializer.data
        temp_data['schedule'] = schedule_serializer.data

        return Response(temp_data)


class DoctorBlockCalendarViewSet(OndocViewSet):

    serializer_class = serializers.DoctorLeaveSerializer
    permission_classes = (IsAuthenticated, DoctorPermission,)
    INTERVAL_MAPPING = {models.DoctorLeave.INTERVAL_MAPPING.get(key): key for key in
                        models.DoctorLeave.INTERVAL_MAPPING.keys()}

    def get_queryset(self):
        user = self.request.user
        return models.DoctorLeave.objects.filter(doctor=user.doctor.id, deleted_at__isnull=True)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = serializers.DoctorLeaveSerializer(queryset, many=True)
        return Response(serializer.data)

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = serializers.DoctorBlockCalenderSerialzer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        doctor_leave_data = {
            "doctor": request.user.doctor.id,
            "start_time": self.INTERVAL_MAPPING[validated_data.get("interval")][0],
            "end_time": self.INTERVAL_MAPPING[validated_data.get("interval")][1],
            "start_date": validated_data.get("start_date"),
            "end_date": validated_data.get("end_date")
        }
        doctor_leave_serializer = serializers.DoctorLeaveSerializer(data=doctor_leave_data)
        doctor_leave_serializer.is_valid(raise_exception=True)
        self.get_queryset().update(deleted_at=timezone.now())
        doctor_leave_serializer.save()
        return Response(doctor_leave_serializer.data)

    def destroy(self, request, pk=None):
        current_time = timezone.now()
        doctor_leave = models.DoctorLeave.objects.get(pk=pk)
        doctor_leave.deleted_at = current_time
        doctor_leave.save()
        return Response({
            "status": 1
        })


class PrescriptionFileViewset(OndocViewSet):
    serializer_class = serializers.PrescriptionFileSerializer

    permission_classes = (IsAuthenticated, )

    def get_queryset(self):
        request = self.request
        if request.user.user_type == User.DOCTOR:
            return models.PrescriptionFile.objects.filter(prescription__appointment__doctor=request.user.doctor)
        elif request.user.user_type == User.CONSUMER:
            return models.PrescriptionFile.objects.filter(prescription__appointment__user=request.user)
        else:
            return models.PrescriptionFile.objects.none()

    def list(self, request, *args, **kwargs):
        appointment = request.query_params.get("appointment")
        if not appointment:
            return Response(status=400)
        queryset = self.get_queryset().filter(prescription__appointment=appointment)
        serializer = serializers.PrescriptionFileSerializer(queryset, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = serializers.PrescriptionSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        if models.Prescription.objects.filter(appointment=validated_data.get('appointment')).exists():
            prescription = models.Prescription.objects.filter(appointment=validated_data.get('appointment')).first()
        else:
            prescription = models.Prescription.objects.create(appointment=validated_data.get('appointment'),
                                                              prescription_details=validated_data.get(
                                                                  'prescription_details'))
        prescription_file_data = {
            "prescription": prescription.id,
            "file": validated_data.get('file')
        }
        prescription_file_serializer = serializers.PrescriptionFileSerializer(data=prescription_file_data)
        prescription_file_serializer.is_valid(raise_exception=True)
        prescription_file_serializer.save()
        return Response(prescription_file_serializer.data)

    def remove(self, request):
        serializer_data = serializers.PrescriptionFileDeleteSerializer(data=request.data, context={'request': request})
        serializer_data.is_valid(raise_exception=True)
        validated_data = serializer_data.validated_data
        response = {
            "status": 0,
            "id": validated_data['id']
        }
        if validated_data.get('id'):
            get_object_or_404(models.PrescriptionFile, pk=validated_data['id'])
            delete_queryset = self.get_queryset().filter(pk=validated_data['id'])
            delete_queryset.delete()
            response['status'] = 1
            return Response(response)
        else:
            return Response(response)


class SearchedItemsViewSet(viewsets.GenericViewSet):
    # permission_classes = (IsAuthenticated, DoctorPermission,)

    def list(self, request, *args, **kwargs):
        medical_conditions = models.MedicalCondition.objects.all().values("id", "name")
        specializations = models.Specialization.objects.all().values("id", "name")
        return Response({"conditions": medical_conditions, "specializations": specializations})


class DoctorListViewSet(viewsets.GenericViewSet):
    # permission_classes = (IsAuthenticated, DoctorPermission,)
    queryset = models.Doctor.objects.all()

    def get_filtering_params(self, data):
        """Helper function that prepare dynamic query for filtering"""
        HOSPITAL_TYPE_MAPPING = {hospital_type[1]: hospital_type[0] for hospital_type in
                                 models.Hospital.HOSPITAL_TYPE_CHOICES}

        filtering_params = []
        if data.get("specialization_ids"):
            filtering_params.append(
                "sp.id IN({})".format(",".join(data.get("specialization_ids")))
            )
        if data.get("sits_at"):
            filtering_params.append(
                "hospital_type IN({})".format(", ".join([str(HOSPITAL_TYPE_MAPPING.get(sits_at)) for sits_at in
                                                         data.get("sits_at")]))
            )
        if data.get("min_fees"):
            filtering_params.append(
                "fees>={}".format(str(data.get("min_fees"))))
        if data.get("max_fees"):
            filtering_params.append(
                "fees<={}".format(str(data.get("max_fees"))))
        if data.get("is_female"):
            filtering_params.append(
                "gender='f'"
            )
        if data.get("is_available"):
            current_time = timezone.now()
            filtering_params.append(
                'dh.day={} and dh.end>{}'.format(str(current_time.day), str(current_time.hour))
            )
        if not filtering_params:
            return "1=1"
        return " and ".join(filtering_params)

    def list(self, request, *args, **kwargs):
        MAX_DISTANCE = "10000000000"
        serializer = serializers.DoctorListSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        longitude = str(validated_data.get("longitude"))
        latitude = str(validated_data.get("latitude"))
        filtering_params = self.get_filtering_params(validated_data)
        order_by_field = 'distance'
        rank_by = "rank_distance=1"
        if validated_data.get('sort_on'):
            if validated_data.get('sort_on') == 'experience':
                order_by_field = 'practicing_since'
            if validated_data.get('sort_on') == 'fees':
                order_by_field = "fees"
                rank_by = "rank_fees=1"
        query_string = 'select x.*, ' \
                       '(select json_agg(to_json(dh.*)) from doctor_hospital dh ' \
                       'where dh.doctor_id=x.doctor_id and dh.hospital_id = x.hospital_id) timings, ' \
                       '(select json_agg(to_json(de.*)) ' \
                       'from doctor_experience de where de.doctor_id=x.doctor_id) experiences, ' \
                       '(SELECT Json_agg(To_json(doctor_images.*)) from ' \
                       '(select di.name from doctor_image di ' \
                       'WHERE  di.doctor_id=x.doctor_id) doctor_images) images, ' \
                       '(SELECT count(distinct dh_subq.hospital_id) as hospital_count ' \
                       'FROM   doctor_hospital dh_subq ' \
                       'WHERE  dh_subq.doctor_id=x.doctor_id), ' \
                       '((select json_agg(to_json(qualification.*)) ' \
                       'from (select dq.passing_year as passing_year,  q.name as qualification, clg.name as college, ' \
                       'spl.name as specialization ' \
                       'from doctor_qualification dq ' \
                       'left join ' \
                       'qualification q on dq.qualification_id=q.id ' \
                       'left join college clg  on dq.college_id = clg.id ' \
                       'left join specialization spl on dq.specialization_id = spl.id ' \
                       'where dq.doctor_id=x.doctor_id ) qualification)) qualifications ' \
                       'from (select row_number() over(partition by d.id order by dh.fees asc) rank_fees, ' \
                       'row_number() over(partition by d.id order by  st_distance(st_setsrid(st_point(%s,%s),4326), ' \
                       'h.location) asc) rank_distance, ' \
                       'st_distance(st_setsrid(st_point(%s,%s),4326),h.location) distance,' \
                       'd.id doctor_id,d.name as name, d.practicing_since, dh.fees as fees,h.name as hospital_name, ' \
                       'd.about,  d.additional_details, d.license, ' \
                       'h.id hospital_id, ' \
                       'h.locality as hospital_address, d.gender as gender  ' \
                       'from doctor d inner join doctor_hospital dh on d.id = dh.doctor_id ' \
                       'inner join hospital h on h.id = dh.hospital_id ' \
                       'left join doctor_qualification dq on dq.doctor_id = d.id ' \
                       'left join specialization sp on sp.id = dq.specialization_id ' \
                       'where %s ' \
                       'order by %s asc ' \
                       ') x ' \
                       'where distance < %s and %s ' % (longitude, latitude,
                                                        longitude, latitude,
                                                        filtering_params, order_by_field,
                                                        MAX_DISTANCE, rank_by)
        paginated_query_string = paginate_raw_query(request, query_string)
        result = RawSql(paginated_query_string).fetch_all()
        for value in result:
            value.update({
                "hospitals": [
                    {
                        "doctor": value.get("name"),
                        "hospital_name": value.get("hospital_name"),
                        "address": value.get("hospital_address"),
                        "fees": value.get("fees"),
                        "hospital_id": value.get("hospital_id"),
                        "discounted_fees": value.get("fees"),
                        "timings": convert_timings(timings=value.get("timings"),
                                                   is_day_human_readable=False)
                    }
                ],
                "id": value.get("doctor_id"),
                "experiences":  [] if not value.get("experiences") else value.get("experiences"),
                "images": [] if not value.get("images") else [
                    {"name": "/media/{}".format(value["images"][0].get("name"))}],
                "languages": [],
                "mobiles": [],
                "medical_services": [],
                "associations": [],
                "awards": [],
                "experience_years": None,
                "data_status": None
            })
            value.pop("timings")
        response_data = {
            "count": 10,
            "result": result
        }
        return Response(response_data)


class DoctorAvailabilityTimingViewSet(viewsets.ViewSet):

    def list(self, request, *args, **kwargs):
        serializer = serializers.DoctorAvailabilityTimingSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        queryset = models.DoctorHospital.objects.filter(doctor=validated_data.get('doctor_id'),
                                                        hospital=validated_data.get('hospital_id'))
        doctor_queryset = (models.Doctor
                           .objects.prefetch_related("qualifications__qualification",
                                                     "qualifications__specialization")
                           .filter(pk=validated_data.get('doctor_id').id))
        doctor_serializer = serializers.DoctorTimeSlotSerializer(doctor_queryset, many=True)

        timeslots = dict()
        obj = TimeSlotExtraction()

        for data in queryset:
            obj.form_time_slots(data.day, data.start, data.end, data.fees, True)

        # resp_dict = obj.get_timing()
        timeslots = obj.get_timing_list()




        # for i in range(0, 7):
        #     timeslots[i] = dict()
        # timeslot_serializer = TimeSlotSerializer(queryset, context={'timing': timeslots}, many=True)
        # data = timeslot_serializer.data
        # for i in range(7):
        #     if timeslots[i].get('timing'):
        #         temp_list = list()
        #         temp_list = [[k, v] for k, v in timeslots[i]['timing'][0].items()]
        #         timeslots[i]['timing'][0] = temp_list
        #         temp_list = [[k, v] for k, v in timeslots[i]['timing'][1].items()]
        #         timeslots[i]['timing'][1] = temp_list
        #         temp_list = [[k, v] for k, v in timeslots[i]['timing'][2].items()]
        #         timeslots[i]['timing'][2] = temp_list
        return Response({"timeslots": timeslots, "doctor_data": doctor_serializer.data})