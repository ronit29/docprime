from rest_framework import serializers
from ondoc.procedure.models import Procedure, DoctorClinicProcedure, ProcedureToCategoryMapping, CommonProcedureCategory


class ProcedureSerializer(serializers.ModelSerializer):
    model = Procedure
    fields = ('id', 'name')


class ProcedureInSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = Procedure
        fields = ('id'
                  , 'name'
                  , 'details')

    def get_name(self, obj):  # Find a parent name in which it lies
        name = '{}'.format(obj.name)
        parent = obj.get_primary_parent_category()
        if parent:
            name += ' in {}'.format(parent.name)
        return name


class DoctorClinicProcedureSerializer(serializers.ModelSerializer):
    procedure = ProcedureInSerializer(read_only=True)
    hospital_id = serializers.ReadOnlyField(source='doctor_clinic.hospital.pk')
    procedure_category_id = serializers.SerializerMethodField()
    procedure_category_name = serializers.SerializerMethodField()
    doctor_clinic = None

    class Meta:
        model = DoctorClinicProcedure
        fields = ('hospital_id', 'procedure', 'mrp', 'agreed_price', 'deal_price',
                  'procedure_category_id', 'procedure_category_name')

    def get_procedure_category_id(self, obj):
        parent = obj.procedure.get_primary_parent_category()
        if parent:
            return parent.pk

    def get_procedure_category_name(self, obj):
        parent = obj.procedure.get_primary_parent_category()
        if parent:
            return parent.name


class DoctorClinicProcedureDetailSerializer(serializers.Serializer):
    doctor_clinic = serializers.IntegerField()
    procedure = serializers.IntegerField(required=False)


class CommonProcedureCategorySerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField(source='procedure_category.id')
    name = serializers.ReadOnlyField(source='procedure_category.name')

    class Meta:
        model = CommonProcedureCategory
        fields = ['id', 'name']
