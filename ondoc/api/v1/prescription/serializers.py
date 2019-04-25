from rest_framework import serializers
from django.db.models import Q
from ondoc.prescription import models as prescription_models
from ondoc.doctor import models as doc_models


class PrescriptionComponents():
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
    quantity = serializers.IntegerField(required=False)
    time = serializers.CharField(max_length=64)
    duration_type = serializers.ChoiceField(choices=prescription_models.PrescriptionMedicine.DURATION_TYPE_CHOICES, required=False)
    duration = serializers.IntegerField(required=False)
    instruction = serializers.CharField(max_length=256, required=False)
    additional_notes = serializers.CharField(max_length=256, required=False)

    def validate(self, attrs):
        if attrs.get('duration_type'):
            attrs['durationstring'] = dict(prescription_models.PrescriptionMedicine.DURATION_TYPE_CHOICES)[attrs['duration_type']]

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
    age = serializers.IntegerField(required=False)
    gender = serializers.CharField(max_length=6)
    phone_number = serializers.IntegerField(required=False, allow_null=True)


class PrescriptionComponentBodySerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=PrescriptionComponents.COMPONENT_CHOICES)
    name = serializers.CharField(max_length=64)
    hospital_id = serializers.PrimaryKeyRelatedField(queryset=doc_models.Hospital.objects.all())


class PrescriptionComponentSyncSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=PrescriptionComponents.COMPONENT_CHOICES)
    hospital_id = serializers.PrimaryKeyRelatedField(queryset=doc_models.Hospital.objects.all(), required=False)


class GeneratePrescriptionPDFBodySerializer(serializers.Serializer):
    symptoms_complaints = serializers.ListField(child=PrescriptionSymptomsComplaintsBodySerializer(), allow_empty=True)
    tests = serializers.ListField(child=PrescriptionTestsBodySerializer(),required=False, allow_empty=True)
    special_instructions = serializers.ListField(child=PrescriptionSpecialInstructionsBodySerializer(), allow_empty=True)
    diagnoses = serializers.ListField(child=PrescriptionDiagnosesBodySerializer(),required=False, allow_empty=True)
    patient_details = PrescriptionPatientSerializer()
    medicines = serializers.ListField(child=PrescriptionMedicineBodySerializer(),required=False, allow_empty=True)
    appointment_id = serializers.CharField(required=False)
    appointment_type = serializers.ChoiceField(choices=prescription_models.PresccriptionPdf.APPOINTMENT_TYPE_CHOICES, required=False)
    followup_date = serializers.DateTimeField(required=False, allow_null=True)
    followup_reason = serializers.CharField(required=False, allow_null=True)

    def validate(self, attrs):
        if attrs:
            appointment = PrescriptionAppointmentValidation.validate_appointment_object(attrs)
            attrs['appointment'] = appointment
        return attrs


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
                  'pdf_file', 'diagnoses', 'lab_tests', 'followup_instructions_date', 'followup_instructions_reason')