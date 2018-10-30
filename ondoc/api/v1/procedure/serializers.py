from rest_framework import serializers
from ondoc.procedure.models import Procedure, DoctorClinicProcedure


class ProcedureSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = Procedure
        fields = ('id', 'name', 'details')

    def get_name(self, obj):
        name = '{}'.format(obj.name)
        if obj.categories.count():
            parent = obj.categories.all().first()
            name += ' in {}'.format(parent.name)
        return name


class DoctorClinicProcedureSerializer(serializers.ModelSerializer):
    procedure = ProcedureSerializer(read_only=True)

    class Meta:
        model = DoctorClinicProcedure
        fields = ('procedure', 'mrp', 'agreed_price', 'listing_price')


class DoctorClinicProcedureDetailSerializer(serializers.Serializer):
    doctor_clinic = serializers.IntegerField()
    procedure = serializers.IntegerField(required=False)
