import re

from rest_framework import serializers

from ondoc.diagnostic import models as diag_models
from ondoc.doctor import models as doc_models
from ondoc.prescription import models as prescription_models


class PrescriptionModelComponents():
    SYMPTOMS_COMPLAINTS=1
    MEDICINES = 2
    SPECIAL_INSTRUCTIONS = 3
    TESTS = 4
    DIAGNOSES = 5
    COMPONENT_CHOICES = [(SYMPTOMS_COMPLAINTS, prescription_models.PrescriptionSymptomsComplaints), (MEDICINES, prescription_models.PrescriptionMedicine),
                         (SPECIAL_INSTRUCTIONS, prescription_models.PrescriptionSpecialInstructions), (TESTS, prescription_models.PrescriptionTests),
                         (DIAGNOSES, prescription_models.PrescriptionDiagnoses)]


class PrescriptionAppointmentValidation():

    @staticmethod
    def validate_uuid(uuid):
        pattern = re.compile(r'^[\da-f]{8}-([\da-f]{4}-){3}[\da-f]{12}$', re.IGNORECASE)
        return True if pattern.match(uuid) else False

    @staticmethod
    def validate_appointment_key(parent, attrs):
        if not parent and ((not 'appointment_id' in attrs  or not 'appointment_type' in attrs) or
                                (not('appointment_id') or not('appointment_type'))):
            raise serializers.ValidationError('Appointment data invalid')
        return attrs

    @staticmethod
    def validate_appointment_object(attrs):
        if attrs and attrs.get('appointment_type') == prescription_models.PresccriptionPdf.OFFLINE:
            queryset = doc_models.OfflineOPDAppointments.objects.select_related('doctor', 'hospital', 'user').prefetch_related('eprescription').filter(id=attrs.get('appointment_id'))
        elif attrs.get('appointment_type') == prescription_models.PresccriptionPdf.DOCPRIME_OPD:
            queryset = doc_models.OpdAppointment.objects.select_related('doctor', 'hospital', 'profile').prefetch_related('eprescription').filter(id=attrs.get('appointment_id'))
        appointment_object = queryset.first()
        if not appointment_object:
            raise serializers.ValidationError('No Appointment found')
        if not appointment_object.status == doc_models.OpdAppointment.COMPLETED:
            raise serializers.ValidationError('Appointment not completed')
        return appointment_object


class PrescriptionMedicineBodySerializer(serializers.Serializer):
    id = serializers.CharField(max_length=100)
    name = serializers.CharField(max_length=128)
    # quantity = serializers.IntegerField(required=False, allow_null=True)
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    dosage_type = serializers.CharField(max_length=100, required=False, allow_blank=True)
    # time = serializers.ListField(child=serializers.CharField(max_length=64), allow_empty=True, required=False)
    time = serializers.ListField(child=serializers.ChoiceField(prescription_models.PrescriptionMedicine.TIME_CHOICES), allow_null=True, required=False)
    custom_time = serializers.CharField(max_length=20, required=False, allow_null=True)
    duration_type = serializers.ChoiceField(choices=prescription_models.PrescriptionMedicine.DURATION_TYPE_CHOICES, required=False, allow_null=True)
    duration = serializers.IntegerField(required=False, allow_null=True)
    is_before_meal = serializers.NullBooleanField(required=False)
    additional_notes = serializers.CharField(max_length=256, required=False, allow_null=True)

    def validate(self, attrs):
        if not PrescriptionAppointmentValidation.validate_uuid(attrs.get("id")):
            raise serializers.ValidationError("Invalid UUID - {}".format(attrs.get('id')))
        if attrs.get('duration_type'):
            attrs['durationstring'] = dict(prescription_models.PrescriptionMedicine.DURATION_TYPE_CHOICES)[attrs['duration_type']]
        if (attrs.get("quantity") or attrs.get("dosage_type")) and not (attrs.get("quantity") and attrs.get("dosage_type")):
            raise serializers.ValidationError("dosage quantity and type both are required together")
        if attrs.get("quantity"):
            attrs["quantity"] = str(attrs["quantity"].normalize())
        if attrs.get("time") and attrs.get("custom_time"):
            raise serializers.ValidationError("only one of the time and custom_time is required")
        return attrs


class PrescriptionSymptomsComplaintsBodySerializer(serializers.Serializer):
    id = serializers.CharField(max_length=100)
    name = serializers.CharField(max_length=128)

    def validate(self, attrs):
        if not PrescriptionAppointmentValidation.validate_uuid(attrs.get("id")):
            raise serializers.ValidationError("Invalid UUID - {}".format(attrs.get('id')))
        return attrs


class PrescriptionTestsBodySerializer(serializers.Serializer):
    id = serializers.CharField(max_length=100)
    name = serializers.CharField(max_length=128)
    instructions = serializers.CharField(max_length=256, required=False, allow_blank=True)

    def validate(self, attrs):
        if not (PrescriptionAppointmentValidation.validate_uuid(attrs.get("id")) or attrs.get('id').isdigit()):
            raise serializers.ValidationError("Invalid UUID or not a number- {}".format(attrs.get('id')))
        return attrs


class PrescriptionSpecialInstructionsBodySerializer(serializers.Serializer):
    id = serializers.CharField(max_length=100)
    name = serializers.CharField(max_length=128)

    def validate(self, attrs):
        if not PrescriptionAppointmentValidation.validate_uuid(attrs.get("id")):
            raise serializers.ValidationError("Invalid UUID - {}".format(attrs.get('id')))
        return attrs


class PrescriptionDiagnosesBodySerializer(serializers.Serializer):
    id = serializers.CharField(max_length=100)
    name = serializers.CharField(max_length=128)

    def validate(self, attrs):
        if not PrescriptionAppointmentValidation.validate_uuid(attrs.get("id")):
            raise serializers.ValidationError("Invalid UUID - {}".format(attrs.get('id')))
        return attrs


class PrescriptionPatientSerializer(serializers.Serializer):
    id = serializers.CharField(max_length=100)
    name = serializers.CharField(max_length=64)
    age = serializers.IntegerField(required=False, allow_null=True)
    gender = serializers.CharField(max_length=6)
    phone_number = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, attrs):
        if not (PrescriptionAppointmentValidation.validate_uuid(attrs.get("id")) or attrs.get('id').isdigit()):
            raise serializers.ValidationError("Invalid UUID or not a number- {}".format(attrs.get('id')))
        return attrs


class PrescriptionSymptomsComplaintsModelSerializer(serializers.ModelSerializer):

    class Meta:
        model = prescription_models.PrescriptionSymptomsComplaints
        fields = "__all__"


class PrescriptionMedicineModelSerializer(serializers.ModelSerializer):

    class Meta:
        model = prescription_models.PrescriptionMedicine
        fields = "__all__"


class PrescriptionSpecialInstructionsModelSerializer(serializers.ModelSerializer):

    class Meta:
        model = prescription_models.PrescriptionSpecialInstructions
        fields = "__all__"


class PrescriptionTestsModelSerializer(serializers.ModelSerializer):

    class Meta:
        model = prescription_models.PrescriptionTests
        fields = "__all__"


class PrescriptionDiagnosesModelSerializer(serializers.ModelSerializer):

    class Meta:
        model = prescription_models.PrescriptionDiagnoses
        fields = "__all__"


class PrescriptionComponentBodySerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=PrescriptionModelComponents.COMPONENT_CHOICES)
    name = serializers.CharField(max_length=64)
    hospital_id = serializers.PrimaryKeyRelatedField(queryset=doc_models.Hospital.objects.all())
    source_type = serializers.ChoiceField(choices=prescription_models.PrescriptionEntity.SOURCE_TYPE_CHOICES)

    def validate(self, attrs):
        model = dict(PrescriptionModelComponents.COMPONENT_CHOICES)[attrs.get('type')]
        if attrs.get("type") == PrescriptionModelComponents.TESTS and diag_models.LabTest.objects.filter(name__iexact=attrs.get("name")).exists():
            raise serializers.ValidationError("Lab Test already exists")
        return attrs


class BulkCreatePrescriptionComponentSerializer(serializers.Serializer):
    data = serializers.ListField(child=PrescriptionComponentBodySerializer(many=False))


class PrescriptionComponentSyncSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=PrescriptionModelComponents.COMPONENT_CHOICES)
    hospital_id = serializers.PrimaryKeyRelatedField(queryset=doc_models.Hospital.objects.all(), required=False)
    updated_at = serializers.DateField(format="%Y-%m-%d", required=False)


class GeneratePrescriptionPDFBodySerializer(serializers.Serializer):
    id = serializers.CharField(max_length=100)
    symptoms_complaints = serializers.ListField(child=PrescriptionSymptomsComplaintsBodySerializer(), allow_empty=True, required=False)
    lab_tests = serializers.ListField(child=PrescriptionTestsBodySerializer(),required=False, allow_empty=True)
    special_instructions = serializers.ListField(child=PrescriptionSpecialInstructionsBodySerializer(), allow_empty=True, required=False)
    diagnoses = serializers.ListField(child=PrescriptionDiagnosesBodySerializer(), required=False, allow_empty=True)
    medicines = serializers.ListField(child=PrescriptionMedicineBodySerializer(),required=False, allow_empty=True)
    patient_details = PrescriptionPatientSerializer()
    appointment_id = serializers.CharField()
    appointment_type = serializers.ChoiceField(choices=prescription_models.PresccriptionPdf.APPOINTMENT_TYPE_CHOICES, required=False)
    followup_instructions_date = serializers.DateTimeField(required=False, allow_null=True)
    followup_instructions_reason = serializers.CharField(required=False, allow_null=True)

    def validate(self, attrs):
        if attrs:
            if not PrescriptionAppointmentValidation.validate_uuid(attrs.get("id")):
                raise serializers.ValidationError("Invalid UUID - {}".format(attrs.get('id')))
            if not (attrs.get('lab_tests') or attrs.get('medicines')):
                raise serializers.ValidationError("Either one of test or medicines is required for prescription generation")

            appointment = PrescriptionAppointmentValidation.validate_appointment_object(attrs)
            attrs['appointment'] = appointment
            if not appointment.doctor.license:
                raise serializers.ValidationError("Registration Number is required for Generating Prescription")

            serial_id = prescription_models.PresccriptionPdf.get_serial(appointment)
            exists = False
            i=0
            for pres in appointment.eprescription.all():
                i=+1
                if str(pres.id) == attrs.get("id"):
                    attrs['task'] = prescription_models.PresccriptionPdf.UPDATE
                    attrs['prescription_pdf'] = pres
                    version = str(int(pres.serial_id[-2:]) + 1).zfill(2)
                    attrs['serial_id'] = pres.serial_id[-12:-2] + version
                    exists = True
                    break
            if not exists:
                if i!=0:
                    attrs['task'] = prescription_models.PresccriptionPdf.CREATE
                    file_no = str(int(serial_id[-5:-3]) + 1).zfill(2)
                    attrs['serial_id'] = serial_id[-12:-5] + file_no + '-01'
                else:
                    attrs['task'] = prescription_models.PresccriptionPdf.CREATE
                    attrs['serial_id'] = str(int(serial_id[-12:-6]) + 1) + '-01-01'
        return attrs


class OfflineOPDAppointmentModelSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()

    def get_user(self, obj):
        if obj.user:
            return str(obj.user.id)

    class Meta:
        model = doc_models.OfflineOPDAppointments
        fields = '__all__'


class OPDAppointmentModelSerializer(serializers.ModelSerializer):

    class Meta:
        model = doc_models.OpdAppointment
        fields = '__all__'


class PrescriptionPDFModelSerializer(serializers.ModelSerializer):
    offline_opd_appointment = OfflineOPDAppointmentModelSerializer()
    opd_appointment = OPDAppointmentModelSerializer()

    class Meta:
        model = prescription_models.PresccriptionPdf
        fields = '__all__'


class PrescriptionResponseSerializer(serializers.ModelSerializer):

    pdf_file = serializers.SerializerMethodField()
    appointment_id = serializers.SerializerMethodField()

    def get_pdf_file(self, obj):
        request = self.context.get('request')
        if obj and obj.prescription_file and request:
            return request.build_absolute_uri(obj.prescription_file.url)
        return None

    def get_appointment_id(self, obj):
        return obj.opd_appointment.id if obj.opd_appointment else obj.offline_opd_appointment.id

    class Meta:
        model = prescription_models.PresccriptionPdf
        fields = ('medicines', 'special_instructions', 'symptoms_complaints', 'appointment_type', 'pdf_file',
                  'diagnoses', 'lab_tests', 'followup_instructions_date', 'followup_instructions_reason', 'updated_at',
                  'appointment_id', 'id', 'serial_id')


class PrescriptionModelSerializerComponents():
    SYMPTOMS_COMPLAINTS=1
    MEDICINES = 2
    SPECIAL_INSTRUCTIONS = 3
    TESTS = 4
    DIAGNOSES = 5
    COMPONENT_CHOICES = [(SYMPTOMS_COMPLAINTS, PrescriptionSymptomsComplaintsModelSerializer), (MEDICINES, PrescriptionMedicineModelSerializer),
                         (SPECIAL_INSTRUCTIONS, PrescriptionSpecialInstructionsModelSerializer), (TESTS, PrescriptionTestsModelSerializer),
                         (DIAGNOSES, PrescriptionDiagnosesModelSerializer)]


class PrescriptionLabTestSerializer(serializers.ModelSerializer):

    moderated = serializers.ReadOnlyField(default=True)
    hospitals = serializers.ReadOnlyField(default=[])
    source_type = serializers.ReadOnlyField(default=None)
    instructions = serializers.ReadOnlyField(default=None)

    class Meta:
        model = diag_models.LabTest
        fields = ('id', 'name', 'created_at', 'updated_at', 'moderated', 'hospitals', 'source_type', 'instructions')
