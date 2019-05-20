from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ondoc.api.v1.auth.views import AppointmentViewSet
from ondoc.authentication.backends import JWTAuthentication
from ondoc.common.utils import get_all_upcoming_appointments
from ondoc.coupon.models import CouponRecommender
from ondoc.doctor.models import CommonSpecialization
from ondoc.diagnostic.models import CommonTest
from ondoc.diagnostic.models import CommonPackage
from ondoc.banner.models import Banner
from ondoc.common.models import PaymentOptions, UserConfig
from ondoc.tracking.models import TrackingEvent
from ondoc.common.models import UserConfig
from ondoc.ratings_review.models import AppRatings
from ondoc.api.v1.doctor.serializers import CommonSpecializationsSerializer
from ondoc.api.v1.diagnostic.serializers import CommonTestSerializer
from ondoc.api.v1.diagnostic.serializers import CommonPackageSerializer


class ScreenViewSet(viewsets.GenericViewSet):

    # authentication_classes = (JWTAuthentication,)
    # permission_classes = (IsAuthenticated,)


    def home_page(self, request, *args, **kwargs):

        show_search_header = True
        show_footer = True
        grid_size = 6
        force_update_version = ""
        update_version = ""
        app_custom_data = None

        params = request.query_params
        from_app = params.get("from_app", False)
        if from_app == 'True' or from_app == 'true':
            from_app=True
        else:
            from_app=False
        coupon_code = params.get('coupon_code')
        profile = params.get('profile_id')
        product_id = params.get('product_id')
        app_version = params.get("app_version", "1.0")
        lat = params.get('lat', None)
        long = params.get('long', None)
        if UserConfig.objects.filter(key="app_update").exists():
            app_update = UserConfig.objects.filter(key="app_update").values_list('data', flat=True).first()
            if app_update:
                force_update_version = app_update.get("force_update_version", "")
                update_version = app_update.get("update_version", "")

        if UserConfig.objects.filter(key="app_custom_data").exists():
            app_custom_data = UserConfig.objects.filter(key="app_custom_data").values_list('data', flat=True).first()

        common_specializations = CommonSpecialization.get_specializations(grid_size-1)
        specializations_serializer = CommonSpecializationsSerializer(common_specializations, many=True,
                                                                                 context={'request': request})

        test_queryset = CommonTest.get_tests(grid_size-1)
        test_serializer = CommonTestSerializer(test_queryset, many=True, context={'request': request})

        package_queryset = CommonPackage.get_packages(grid_size-1)
        coupon_recommender = CouponRecommender(request.user, profile, 'lab', product_id, coupon_code, None)
        package_serializer = CommonPackageSerializer(package_queryset, many=True, context={'request': request, 'coupon_recommender': coupon_recommender})

        # upcoming_appointment_viewset = AppointmentViewSet()
        # upcoming_appointment_result = upcoming_appointment_viewset.upcoming_appointments(request).data
        upcoming_appointment_result = []
        if request.user.is_authenticated:
            upcoming_appointment_result = get_all_upcoming_appointments(request.user.id)

        grid_list = [
            {
                'priority': 2,
                'title': "Book Doctor Appointment",
                'type': "Specialization",
                'items': specializations_serializer.data,
                'tag': "Upto 50% off",
                'tagColor': "#ff0000",
                'addSearchItem': "Doctor"
            },
            {
                'priority': 0,
                'title': "Health Packages",
                'type': "CommonPackage",
                'items': package_serializer.data,
                'tag': "Upto 50% off",
                'tagColor': "#ff0000",
                'addSearchItem': "Package"
            },
            {
                'priority': 3,
                'title': "Book a Test",
                'type': "CommonTest",
                'items': test_serializer.data,
                'tag': "Upto 50% off",
                'tagColor': "#ff0000",
                'addSearchItem': "Lab"
            }
        ]

        banner_list = Banner.get_all_banners(request, lat, long, from_app)
        banner_list_homepage = list()
        for banner in banner_list:
            if banner.get('slider_location') == 'home_page':
                banner_list_homepage.append(banner)
        banner = [{
            'priority': 1,
            'type': "Banners",
            'title': "Banners",
            'items': banner_list_homepage
        }]

        params = request.query_params
        from_app = params.get("from_app", False)
        if from_app:
            queryset = PaymentOptions.objects.filter(is_enabled=True).order_by('-priority')
        else:
            queryset = PaymentOptions.objects.filter(is_enabled=True).order_by('-priority')
        payment_options = PaymentOptions.build_payment_option(queryset)

        resp = {"home":
                    {
                    "show_search_header": show_search_header,
                    "show_footer": show_footer,
                    "grid_list": grid_list,
                    },
                "banner": banner,
                "upcoming_appointments": upcoming_appointment_result,
                "payment_options": payment_options,
                "app_custom_data": app_custom_data,
                "app_force_update": app_version < force_update_version,
                "app_update": app_version < update_version,
                "ask_for_app_rating": self.ask_for_app_rating(request)
        }

        return Response(resp)

    def ask_for_app_rating(self, request, *args, **kwargs):

        app_rating_key = UserConfig.objects.filter(key="APP_RATING_FREQUENCY").values_list('data', flat=True)
        DEFAULT_APP_RATING_FREQUENCY = 5
        if app_rating_key.exists() and len(app_rating_key) == 1 and type(app_rating_key[0]) == int:
                APP_RATING_FREQUENCY = app_rating_key[0]
        else:
                APP_RATING_FREQUENCY = DEFAULT_APP_RATING_FREQUENCY

        if request.user.is_authenticated:
            user = request.user
        else:
            return False
        opd_app = user.get_unrated_opd_appointment()
        lab_app = user.get_unrated_lab_appointment()
        if opd_app or lab_app:
            return False

        if AppRatings.objects.filter(user=user, app_type=AppRatings.CONSUMER).exists():
            return False

        user_tracking = TrackingEvent.objects.filter(user=user, data__Category="DocprimeApp", data__Action="AppLaunch")
        if user_tracking.exists() and user_tracking.count() % APP_RATING_FREQUENCY == 0:
            return True
        else:
            return False