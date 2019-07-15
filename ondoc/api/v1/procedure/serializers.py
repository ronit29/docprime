from rest_framework import serializers

from ondoc.doctor.models import OpdAppointmentProcedureMapping, CommonHospital
from ondoc.procedure.models import Procedure, DoctorClinicProcedure, ProcedureToCategoryMapping, \
    CommonProcedureCategory, CommonProcedure, CommonIpdProcedure


class ProcedureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Procedure
        fields = ('id', 'name', 'details', 'duration', 'is_enabled')


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


class OpdAppointmentProcedureSerializer(serializers.ModelSerializer):


    class Meta:
        model = DoctorClinicProcedure
        fields = ('hospital_id', 'procedure', 'mrp', 'agreed_price', 'deal_price',
                  'procedure_category_id', 'procedure_category_name', 'is_selected')


class OpdAppointmentProcedureMappingSerializer(serializers.ModelSerializer):
    name = serializers.ReadOnlyField(source='procedure.name')

    class Meta:
        model = OpdAppointmentProcedureMapping
        fields = ('name', 'mrp', 'agreed_price', 'deal_price')

        # 'procedure' , 'mrp', 'agreed_price', 'deal_price'


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


class CommonProcedureSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField(source='procedure.id')
    name = serializers.ReadOnlyField(source='procedure.name')

    class Meta:
        model = CommonProcedure
        fields = ['id', 'name']


class CommonIpdProcedureSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField(source='ipd_procedure.id')
    name = serializers.ReadOnlyField(source='ipd_procedure.name')
    url = serializers.SerializerMethodField()
    icon = serializers.SerializerMethodField()

    class Meta:
        model = CommonIpdProcedure
        fields = ['id', 'name', 'url', 'icon']

    def get_url(self, obj):
        entity_dict = self.context.get('entity_dict', {})
        url = entity_dict.get(obj.ipd_procedure.id, None)
        return url

    def get_icon(self, obj):
        url = None
        request = self.context.get('request')
        if request:
            if obj and obj.ipd_procedure and obj.ipd_procedure.icon:
                url = request.build_absolute_uri(obj.ipd_procedure.icon.url)
        return url


class CommonHospitalSerializer(serializers.ModelSerializer):
    # id = serializers.ReadOnlyField(source='ipd_procedure.id')
    # name = serializers.ReadOnlyField(source='ipd_procedure.name')
    # url = serializers.SerializerMethodField()

    class Meta:
        model = CommonHospital
        fields = ['id']
