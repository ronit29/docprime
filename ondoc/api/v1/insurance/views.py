from rest_framework import viewsets
from . import serializers
from rest_framework.response import Response
from ondoc.insurance.models import (Insurer, InsuredMembers)
from ondoc.authentication.models import UserProfile
from ondoc.insurance.models import InsurancePlans
from ondoc.authentication.views import UserProfile


class ListInsuranceViewSet(viewsets.GenericViewSet):

    def get_queryset(self):
        return Insurer.objects.filter()

    def list(self, request):
        insurer_data = self.get_queryset()
        body_serializer = serializers.InsurerSerializer(insurer_data, many=True)

        # body_serializer.is_valid(raise_exception=True)
        # valid_data = body_serializer.validated_data
        return Response(body_serializer.data)


class InsuredMemberViewSet(viewsets.GenericViewSet):

    def create(self, request):
        serializer = serializers.InsuredMemberSerializer(data=request.data.get('members'), many=True)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        insurer = Insurer.objects.get(id=request.data.get('insurer'))
        insurance_plan = InsurancePlans.objects.get(id=request.data.get('insurance_plan'))

        if valid_data:
            if request.data.get('profile'):
                profile = UserProfile.objects.get(id=request.data.get('profile'))
                for members in valid_data:
                    insured_members = InsuredMembers(profile=profile, first_name=members['first_name'],
                                                     last_name=members['last_name'], dob=members['dob'],
                                                     address=members['address'], pincode=members['pincode'],
                                                     email=members['email'], relation=members['relation'],
                                                     insurance_plan=insurance_plan, insurer=insurer)
                    insured_members.save()
            else:
                user_profile = UserProfile.create(request.data.get('member'))
                print(user_profile)




