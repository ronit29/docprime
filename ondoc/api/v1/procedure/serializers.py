from rest_framework import serializers
from ondoc.procedure.models import Procedure


class ProcedureListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Procedure
        fields = ('id', 'name', 'details')

