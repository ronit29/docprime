from rest_framework import serializers
from django.db.models import Q
from ondoc.prescription import models as prescription_models
from ondoc.doctor import models as doc_models
from ondoc.diagnostic import models as diag_models


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
    def validate_appointment_key(parent, attrs):
        if not parent and ((not 'appointment_id' in attrs  or not 'appointment_type' in attrs) or
                                (not('appointment_id') or not('appointment_type'))):
            raise serializers.ValidationError('Appointment data invalid')
        return attrs

    @staticmethod
    def validate_appointment_object(attrs):
        if attrs and attrs.get('appointment_type') == prescription_models.PresccriptionPdf.OFFLINE:
            queryset = doc_models.OfflineOPDAppointments.objects.select_related('doctor', 'hospital', 'user').filter(id=attrs.get('appointment_id'))
        elif attrs.get('appointment_type') == prescription_models.PresccriptionPdf.DOCPRIME_OPD:
            queryset = doc_models.OpdAppointment.objects.select_related('doctor', 'hospital', 'profile').filter(id=attrs.get('appointment_id'))
        appointment_object = queryset.first()
        if not appointment_object:
            raise serializers.ValidationError('No Appointment found')
        if not appointment_object.status == doc_models.OpdAppointment.COMPLETED:
            raise serializers.ValidationError('Appointment not completed')
        return appointment_object


class PrescriptionMedicineBodySerializer(serializers.Serializer):
    name = serializers.CharField(max_length=64)
    quantity = serializers.IntegerField(required=False, allow_null=True)
    dosage_type = serializers.ChoiceField(choices=prescription_models.PrescriptionMedicine.DOSAGE_TYPE_CHOICES, required=False, allow_null=True)
    time = serializers.ListField(child=serializers.CharField(max_length=64), allow_empty=True, required=False)
    duration_type = serializers.ChoiceField(choices=prescription_models.PrescriptionMedicine.DURATION_TYPE_CHOICES, required=False, allow_null=True)
    duration = serializers.IntegerField(required=False, allow_null=True)
    # instruction = serializers.CharField(max_length=256, required=False)
    is_before_meal = serializers.NullBooleanField(required=False)
    additional_notes = serializers.CharField(max_length=256, required=False, allow_null=True)

    def validate(self, attrs):
        if attrs.get('duration_type'):
            attrs['durationstring'] = dict(prescription_models.PrescriptionMedicine.DURATION_TYPE_CHOICES)[attrs['duration_type']]
        if attrs.get("quantity") and not attrs.get("dosage_type"):
            raise serializers.ValidationError("dosage type is also required with quantity")
        return attrs


class PrescriptionSymptomsComplaintsBodySerializer(serializers.Serializer):
    name = serializers.CharField(max_length=64)


class PrescriptionTestsBodySerializer(serializers.Serializer):
    name = serializers.CharField(max_length=64)


class PrescriptionSpecialInstructionsBodySerializer(serializers.Serializer):
    name = serializers.CharField(max_length=64)


class PrescriptionDiagnosesBodySerializer(serializers.Serializer):
    name = serializers.CharField(max_length=64)


class PrescriptionPatientSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=64)
    age = serializers.IntegerField(required=False, allow_null=True)
    gender = serializers.CharField(max_length=6)
    phone_number = serializers.IntegerField(required=False, allow_null=True)


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
    quantity = serializers.IntegerField(required=False)
    dosage_type = serializers.ChoiceField(choices=prescription_models.PrescriptionMedicine.DOSAGE_TYPE_CHOICES, required=False)
    time = serializers.ListField(child=serializers.CharField(max_length=64), allow_empty=True, required=False)
    duration_type = serializers.ChoiceField(choices=prescription_models.PrescriptionMedicine.DURATION_TYPE_CHOICES,
                                            required=False)
    duration = serializers.IntegerField(required=False)
    # instruction = serializers.CharField(max_length=256, required=False)
    is_before_meal = serializers.NullBooleanField(required=False)
    additional_notes = serializers.CharField(max_length=256, required=False)

    def validate(self, attrs):
        model = dict(serializers.PrescriptionModelComponents.COMPONENT_CHOICES)[attrs.get('type')]
        if model.objects.filter(name__iexact=attrs.get('name')).exists():
            raise serializers.ValidationError("component with this name already exists")
        if attrs.get("type") == PrescriptionModelComponents.TESTS and diag_models.LabTest.objects.filter(name__iexact=attrs.get("name")).exists():
            raise serializers.ValidationError("Lab Test already exists")
        return attrs


class PrescriptionComponentSyncSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=PrescriptionModelComponents.COMPONENT_CHOICES)
    hospital_id = serializers.PrimaryKeyRelatedField(queryset=doc_models.Hospital.objects.all(), required=False)


class GeneratePrescriptionPDFBodySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    symptoms_complaints = serializers.ListField(child=PrescriptionSymptomsComplaintsBodySerializer(), allow_empty=True, required=False)
    tests = serializers.ListField(child=PrescriptionTestsBodySerializer(),required=False, allow_empty=True)
    special_instructions = serializers.ListField(child=PrescriptionSpecialInstructionsBodySerializer(), allow_empty=True, required=False)
    diagnoses = serializers.ListField(child=PrescriptionDiagnosesBodySerializer(), required=False, allow_empty=True)
    patient_details = PrescriptionPatientSerializer()
    medicines = serializers.ListField(child=PrescriptionMedicineBodySerializer(),required=False, allow_empty=True)
    appointment_id = serializers.CharField(required=False)
    appointment_type = serializers.ChoiceField(choices=prescription_models.PresccriptionPdf.APPOINTMENT_TYPE_CHOICES, required=False)
    followup_date = serializers.DateTimeField(required=False, allow_null=True)
    followup_reason = serializers.CharField(required=False, allow_null=True)

    def validate(self, attrs):
        if attrs:
            if not (attrs.get('tests') or attrs.get('medicines')):
                raise serializers.ValidationError("Either one of test or medicines is required for prescription generation")
            appointment = PrescriptionAppointmentValidation.validate_appointment_object(attrs)
            attrs['appointment'] = appointment
            if not appointment.doctor.license:
                raise serializers.ValidationError("Registration Number is required for Generating Prescription")
            serial_id = prescription_models.PresccriptionPdf.get_serial(appointment)
            prescription_queryset = prescription_models.PresccriptionPdf.objects.filter(appointment_id=appointment.id)
            if prescription_queryset.exists():
                queryset = prescription_queryset.filter(id=attrs.get("id"))
                if queryset.exists():
                    attrs['task'] = prescription_models.PresccriptionPdf.UPDATE
                    obj = queryset.first()
                    version = str(int(obj.serial_id[-2:]) + 1).zfill(2)
                    attrs['serial_id'] = serial_id[-12:-2] + version
                else:
                    attrs['task'] = prescription_models.PresccriptionPdf.CREATE
                    file_no = str(int(serial_id[-5:-3]) + 1).zfill(2)
                    attrs['serial_id'] = serial_id[-12:-5] + file_no + serial_id[-3:]
            else:
                attrs['task'] = prescription_models.PresccriptionPdf.CREATE
                attrs['serial_id'] = str(int(serial_id[-12:-6]) + 1) + serial_id[-6:]
        return attrs


class PrescriptionPdfModelSerializer(serializers.ModelSerializer):

    class Meta:
        model = prescription_models.PresccriptionPdf
        fields = '__all__'


class PrescriptionResponseSerializer(serializers.ModelSerializer):

    pdf_file = serializers.SerializerMethodField()

    def get_pdf_file(self, obj):
        request = self.context.get('request')
        if obj and obj.prescription_file and request:
            return request.build_absolute_uri(obj.prescription_file.url)
        return None

    class Meta:
        model = prescription_models.PresccriptionPdf
        fields = ('medicines', 'special_instructions', 'symptoms_complaints', 'appointment_id', 'appointment_type',
                  'pdf_file', 'diagnoses', 'lab_tests', 'followup_instructions_date', 'followup_instructions_reason',
                  'updated_at')


class PrescriptionModelSerializerComponents():
    SYMPTOMS_COMPLAINTS=1
    MEDICINES = 2
    SPECIAL_INSTRUCTIONS = 3
    TESTS = 4
    DIAGNOSES = 5
    COMPONENT_CHOICES = [(SYMPTOMS_COMPLAINTS, PrescriptionSymptomsComplaintsModelSerializer), (MEDICINES, PrescriptionMedicineModelSerializer),
                         (SPECIAL_INSTRUCTIONS, PrescriptionSpecialInstructionsModelSerializer), (TESTS, PrescriptionTestsModelSerializer),
                         (DIAGNOSES, PrescriptionDiagnosesModelSerializer)]
