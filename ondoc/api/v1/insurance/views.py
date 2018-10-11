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
        profile = UserProfile.objects.filter(id=request.data.get('profile'))

        if valid_data:
              if not profile:
                    for members in valid_data:
                        name = members.get('first_name') + ' ' + members.get('last_name')
                        phone_number=''
                        gender = ''
                        if members.get('title') == 'Mr.':
                            gender = 'm'
                        elif members.get('title') == 'Mrs.':
                            gender = 'f'
                        members_profile = UserProfile.objects.create(id=request.user.id, name=name,
                                                                     email=members.get('email'), gender=gender,
                                                                     user_id=request.user.pk, dob=members.get('dob'),
                                                                     is_default_user=False, is_otp_verified=False,
                                                                     phone_number=phone_number)
                        print('member profile created')



        # if valid_data:
        #     if request.data.get('profile'):
        #         profile = UserProfile.objects.get(id=request.data.get('profile'))
        #         for members in valid_data:
        #             insured_members = InsuredMembers(profile=profile, first_name=members['first_name'],
        #                                              last_name=members['last_name'], dob=members['dob'],
        #                                              address=members['address'], pincode=members['pincode'],
        #                                              email=members['email'], relation=members['relation'],
        #                                              insurance_plan=insurance_plan, insurer=insurer)
        #             insured_members.save()
        #     else:
        #         user_profile = UserProfile.create(request.data.get('member'))
        #         print(user_profile)




