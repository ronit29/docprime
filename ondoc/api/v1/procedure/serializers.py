from rest_framework import serializers
from ondoc.procedure.models import Procedure, DoctorClinicProcedure, ProcedureToCategoryMapping


class ProcedureSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = Procedure
        fields = ('id', 'name', 'details')

    def get_name(self, obj):
        name = '{}'.format(obj.name)
        parent = None
        if ProcedureToCategoryMapping.objects.filter(is_primary=True, procedure=obj).count():
            temp_queryset = ProcedureToCategoryMapping.objects.filter(is_primary=True, procedure=obj).first()
            parent = temp_queryset.parent_category
        elif obj.categories.count():
            parent = obj.categories.all().first()
        if parent:
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
