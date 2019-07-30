from ondoc.account.models import ConsumerAccount, Order
from ondoc.api.v1.utils import payment_details
from ondoc.authentication.models import UserSecretKey, UserProfile
from ondoc.chat import models
from ondoc.doctor import models as doc_models
from ondoc.authentication import models as auth_models
from ondoc.api.v1.doctor import serializers as doc_serializers
from rest_framework import mixins, viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from ondoc.authentication.backends import JWTAuthentication, ChatAuthentication
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.db import transaction
from . import serializers
from django.conf import settings
import requests, re, json, jwt, decimal
from django.utils import timezone

User = get_user_model()


class ChatSearchedItemsViewSet(viewsets.GenericViewSet):

    @transaction.non_atomic_requests
    def list(self, request, *args, **kwargs):
        medical_conditions = models.ChatMedicalCondition.objects.all().values("id", "name")
        return Response({"conditions": medical_conditions})


class DoctorsListViewSet(viewsets.GenericViewSet):

    authentication_classes = (JWTAuthentication, )
    permission_classes = (IsAuthenticated, )
    queryset = doc_models.Doctor.objects.none()

    @transaction.non_atomic_requests
    def list(self, request, *args, **kwargs):
        queryset = doc_models.Doctor.objects.all().order_by('id')[:20]
        # serializer = serializers.DoctorListSerializer(queryset, many=True)
        serializer = doc_serializers.DoctorProfileSerializer(queryset, many=True, context={"request": request})

        return Response(serializer.data)


class DoctorProfileViewSet(viewsets.GenericViewSet):

    queryset = doc_models.DoctorMapping.objects

    @transaction.non_atomic_requests
    def retrieve(self, request, pk):
        doctor = get_object_or_404(doc_models.Doctor, id=pk)
        response = []
        doc_mapping = doc_models.DoctorMapping.objects.filter(doctor=doctor)
        if doc_mapping.exists():
            doctor = doc_mapping.first().profile_to_be_shown
        if doctor:
            serializer = doc_serializers.DoctorProfileSerializer(doctor, many=False, context={"request": request})
            response = serializer.data
        return Response(response)


class UserProfileViewSet(viewsets.GenericViewSet):

    authentication_classes = (JWTAuthentication, )
    permission_classes = (IsAuthenticated, )

    @transaction.non_atomic_requests
    def retrieve(self, request):
        user_id = request.user.id
        chat_domain = settings.CHAT_API_URL
        try:
            chat_api_url = '%s/api/v1/livechat/healthservices/getProfileChats/%s'%(chat_domain, user_id)
            chat_api_request = requests.get(chat_api_url)
        except:
            return Response([])
        try:
            chat_room_url = '%s/api/v1/livechat/healthservices/getRooms/%s'%(chat_domain, user_id)
            chat_room_request = requests.get(chat_room_url)
        except:
            return Response([])
        if chat_api_request.status_code == 200 and chat_room_request.status_code == 200:
            chat_api_json = chat_api_request.text
            chat_room_json = chat_room_request.text
            if chat_api_json and chat_room_json:
                UserProfiles = auth_models.UserProfile.objects.all()
                Doctors = doc_models.Doctor.objects.all()
                chat_api_data = json.loads(chat_api_json)
                chat_room_data = json.loads(chat_room_json)
                response_data = []
                for room_data in chat_room_data:
                    response = {}
                    response['room_id'] = room_data.get('rid')
                    response['date'] = room_data.get('ts', None)
                    response['doctor_name'] = None
                    response['user_name']=  None
                    try:
                        doc_id = int(room_data.get('user'))
                        if doc_id:
                            for doc in Doctors:
                                if int(doc.id) == int(doc_id):
                                    response['doctor_name'] = doc.name
                                    break
                    except:
                        continue
                    for chat_data in chat_api_data:
                        if room_data.get('rid') == chat_data.get('_id'):
                            small_case_symptoms = chat_data['params'].get('symptoms', None)
                            capital_case_symptoms = chat_data['params'].get('Symptoms', None)
                            symptoms_list = []
                            response['symptoms'] = None
                            if small_case_symptoms:
                                small_symptoms_list = re.sub(r'\s', '', small_case_symptoms).split(',')
                                symptoms_list.extend(small_symptoms_list)
                            if capital_case_symptoms:
                                capital_symptoms_list = re.sub(r'\s', '', capital_case_symptoms).split(',')
                                symptoms_list.extend(capital_symptoms_list)
                            for key in chat_data['params'].keys():
                                assoc_symptom = re.match('^\w+AssociatedSymptoms', key,  re.IGNORECASE)
                                if assoc_symptom:
                                    associated_symptom = chat_data['params'].get(assoc_symptom.group(0), None)
                                    if associated_symptom:
                                        if isinstance(associated_symptom, list):
                                            symptoms_list.extend(associated_symptom)
                                            break
                            if symptoms_list:
                                unique_symptoms_list = set([x.lower() for x in symptoms_list])
                                if unique_symptoms_list:
                                    response['symptoms'] = [x.title() for x in unique_symptoms_list]
                            else:
                                continue
                            selected_profile = chat_data['params'].get('selectedProfile', None)
                            if selected_profile:
                                user_profile_id = selected_profile.get('id')
                                for usr in UserProfiles:
                                    if int(usr.id) == int(user_profile_id):
                                        response['user_name'] = usr.name
                                        break
                            else:
                                continue
                    response_data.append(response)
                return Response(response_data)
        return Response([])


class ChatPrescriptionViewSet(viewsets.GenericViewSet):

    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def retrieve(self, request):

        SUCCESS_OK_STATUS = '1'
        FAILURE_OK_STATUS = '0'

        user = request.user

        url = settings.CHAT_PRESCRIPTION_URL + user.phone_number

        response = requests.get(url=url)

        if response.status_code == status.HTTP_200_OK:
            try:
                resp_data = response.json()
                return Response({"status": SUCCESS_OK_STATUS, "data":resp_data})
            except:
                return Response({"status": FAILURE_OK_STATUS})
        else:
            return Response({"status": FAILURE_OK_STATUS})


class ChatReferralViewSet(viewsets.GenericViewSet):

    def retrieve(self, request):

        serializer = serializers.ChatReferralNumberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        user = validated_data.get('user')
        referral_obj = user.referral.first()
        if referral_obj:
            code = referral_obj.code
            return Response({"status": 1, "code": code})
        else:
            return Response({"status": 0, "code": 'Referral Code not Found'})


class ChatUserViewSet(viewsets.GenericViewSet):
    authentication_classes = (ChatAuthentication,)

    @transaction.atomic()
    def user_login_via_chat(self, request):
        from django.http import JsonResponse
        response = {'login': 0}
        if request.method != 'POST':
            return JsonResponse(response, status=405)

        serializer = serializers.ChatLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        profile_data = {}

        user = User.objects.filter(phone_number=data.get('phone_number'), user_type=User.CONSUMER).first()
        if not user:
            user = User.objects.create(phone_number=data.get('phone_number'),
                                       is_phone_number_verified=False,
                                       user_type=User.CONSUMER,
                                       auto_created=True,
                                       email=data.get('email'),
                                       source='Chat')

        if not user:
            return JsonResponse(response, status=400)

        profile_data['name'] = data.get('name')
        profile_data['phone_number'] = user.phone_number
        profile_data['gender'] = data.get('gender')
        profile_data['user'] = user
        user_profiles = UserProfile.objects.filter(user=user)
        if not user_profiles.exists():
            profile_data.update({
                "is_default_user": True
            })

        if not bool(re.match(r"^[a-zA-Z ]+$", data.get('name'))):
            return Response({"error": "Invalid Name"}, status=status.HTTP_400_BAD_REQUEST)

        if profile_data.get('is_default_user') or not UserProfile.objects.filter(name__iexact=profile_data['name'], user=user).exists():
            user_profile = UserProfile.objects.create(**profile_data)

        consumer_account = ConsumerAccount.objects.get_or_create(user=user)
        wallet_balance = consumer_account[0].get_total_balance()

        token_object = JWTAuthentication.generate_token(user)

        response = {
            "token": token_object['token'],
            "payload": token_object['payload'],
            "wallet_balance": wallet_balance,
            "is_user_insured": user.active_insurance if user.active_insurance else False
        }

        return Response(response, status=status.HTTP_200_OK)


class ChatOrderViewSet(viewsets.GenericViewSet):

    @classmethod
    @transaction.atomic()
    def create_order(self, request):
        from ondoc.notification.tasks import save_pg_response
        from ondoc.account.mongo_models import PgLogs
        user = request.user
        data = request.data

        if user and user.is_anonymous:
            return Response({"status": 0}, status.HTTP_401_UNAUTHORIZED)

        save_pg_response.apply_async((PgLogs.CHAT_ORDER_REQUEST, None, None, None, request.data, user.id),
                                     eta=timezone.localtime(), )

        details = data.get('details', {})
        plan_id = data.get('plan_id')
        use_wallet = data.get('use_wallet', True)
        amount = data.get('amount', 0)
        promotional_amount = data.get('promotional_amount', 0)
        rid = data.get('rid')
        error = False

        try:
            amount = decimal.Decimal(amount)
            promotional_amount = decimal.Decimal(promotional_amount)
            details["promotional_amount"] = float(promotional_amount)
            details = json.dumps(details)
        except:
            error = True

        if error:
            return Response({"status": 0}, status.HTTP_400_BAD_REQUEST)

        resp = {}
        process_immediately = False
        product_id = Order.CHAT_PRODUCT_ID

        consumer_account = ConsumerAccount.objects.get_or_create(user=user)
        consumer_account = ConsumerAccount.objects.select_for_update().get(user=user)

        wallet_balance = consumer_account.balance
        cashback_balance = consumer_account.cashback
        total_balance = wallet_balance + cashback_balance

        amount_to_paid = amount

        if use_wallet and total_balance >= amount:
            cashback_amount = min(cashback_balance, amount_to_paid)
            wallet_amount = max(0, amount_to_paid - cashback_amount)
            amount_to_paid = max(0, amount_to_paid - total_balance)
            process_immediately = True
        elif use_wallet and total_balance < amount:
            cashback_amount = min(amount_to_paid, cashback_balance)
            wallet_amount = 0
            if cashback_amount < amount_to_paid:
                wallet_amount = min(wallet_balance, amount_to_paid - cashback_amount)
            amount_to_paid = max(0, amount_to_paid - total_balance)
            process_immediately = False
        else:
            cashback_amount = 0
            wallet_amount = 0
            process_immediately = False

        action = Order.CHAT_CONSULTATION_CREATE
        action_data = {"user": user.id, "plan_id": plan_id, "extra_details": details, "effective_price": float(amount_to_paid),
                       "amount": float(amount), "cashback": float(cashback_amount), "promotional_amount": float(promotional_amount), "room_id": rid}

        pg_order = Order.objects.create(
            amount=float(amount_to_paid),
            action=action,
            action_data=action_data,
            wallet_amount=wallet_amount,
            cashback_amount=cashback_amount,
            payment_status=Order.PAYMENT_PENDING,
            user=user,
            product_id=product_id
        )

        if process_immediately:
            consultation_ids = pg_order.process_pg_order()
            resp["status"] = 1
            resp["payment_required"] = False
            resp["data"] = {
                "orderId": pg_order.id,
                "type": consultation_ids.get("type", "chat"),
                "id": consultation_ids.get("id", None)
            }
        else:
            resp["status"] = 1
            resp['data'], resp["payment_required"] = payment_details(request, pg_order)

        return Response(resp, status=status.HTTP_200_OK)