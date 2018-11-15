from rest_framework import serializers
from ondoc.procedure.models import Procedure, DoctorClinicProcedure, ProcedureToCategoryMapping, CommonProcedureCategory


class ProcedureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Procedure
        fields = ('id', 'name', 'details', 'duration')


class ProcedureInSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = Procedure
        fields = ('id'
                  , 'name'
                  # , 'details'
                  )

    def get_name(self, obj):  # Find a parent name in which it lies
        name = '{}'.format(obj.name)
        parent = obj.get_primary_parent_category()
        if parent:
            name += ' in {}'.format(parent.name)
        return name


class DoctorClinicProcedureSerializer(serializers.ModelSerializer):
    procedure = ProcedureSerializer(read_only=True)
    hospital_id = serializers.ReadOnlyField(source='doctor_clinic.hospital.pk')
    procedure_category_id = serializers.SerializerMethodField()
    procedure_category_name = serializers.SerializerMethodField()
    is_selected = serializers.SerializerMethodField(default=False)

    class Meta:
        model = DoctorClinicProcedure
        fields = ('hospital_id', 'procedure', 'mrp', 'agreed_price', 'deal_price',
                  'procedure_category_id', 'procedure_category_name', 'is_selected')

    def get_is_selected(self, obj):
        return self.context.get('is_selected', False)

    def get_procedure_category_id(self, obj):
        parent_category_ids = self.context.get('category_ids', None)
        parent = obj.procedure.get_primary_parent_category(parent_category_ids)
        if parent:
            return parent.pk
        return None

    def get_procedure_category_name(self, obj):
        parent_category_ids = self.context.get('category_ids', None)
        parent = obj.procedure.get_primary_parent_category(parent_category_ids)
        if parent:
            return parent.name
        return None


class DoctorClinicProcedureDetailSerializer(serializers.Serializer):
    doctor_clinic = serializers.IntegerField()
    procedure = serializers.IntegerField(required=False)


class CommonProcedureCategorySerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField(source='procedure_category.id')
    name = serializers.ReadOnlyField(source='procedure_category.name')

    class Meta:
        model = CommonProcedureCategory
        fields = ['id', 'name']
