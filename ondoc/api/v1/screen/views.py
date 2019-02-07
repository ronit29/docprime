from rest_framework import viewsets
from rest_framework.response import Response
from ondoc.doctor.models import CommonSpecialization
from ondoc.diagnostic.models import CommonTest
from ondoc.diagnostic.models import CommonPackage
from ondoc.api.v1.doctor.serializers import CommonSpecializationsSerializer
from ondoc.api.v1.diagnostic.serializers import CommonTestSerializer
from ondoc.api.v1.diagnostic.serializers import CommonPackageSerializer
from ondoc.api.v1.common.views import GetPaymentOptionsViewSet
from ondoc.api.v1.banner.views import BannerListViewSet


class ScreenViewSet(viewsets.GenericViewSet):

    def home_page(self, request, *args, **kwargs):

        show_search_header = True
        show_footer = True
        grid_size = 6

        common_specializations = CommonSpecialization.objects.select_related(
            'specialization').all().order_by("priority")[:grid_size-1]
        specializations_serializer = CommonSpecializationsSerializer(common_specializations, many=True,
                                                                                 context={'request': request})

        test_queryset = CommonTest.objects.filter(test__enable_for_retail=True)[:grid_size-1]
        test_serializer = CommonTestSerializer(test_queryset, many=True, context={'request': request})

        package_queryset = CommonPackage.objects.prefetch_related('package').filter(package__enable_for_retail=True)[:grid_size-1]
        package_serializer = CommonPackageSerializer(package_queryset, many=True, context={'request': request})

        banner_obj = BannerListViewSet()
        banner_list = banner_obj.list(request).data
        banner_list_homepage = list()
        for banner in banner_list:
            if banner.get('slider_location') == 'home_page':
                banner_list_homepage.append(banner)

        grid_list = [
            {
                'priority': 0,
                'title': "Find a Doctor",
                'type': "Specialization",
                'items': specializations_serializer.data,
                'tag': "Upto 50% off",
                'tagColor': "#ff0000",
                'addSearchItem': "Doctor"
            },
            #{
            #    'priority': 1,
            #    'type': "Banners",
            #    'title': "Banners",
            #    'items': banner_list_homepage
            #},
            {
                'priority': 2,
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

        payment_obj = GetPaymentOptionsViewSet()

        payment_options = payment_obj.list(request).data

        resp = {"home":
                    {
                    "show_search_header": show_search_header,
                    "show_footer": show_footer,
                    "grid_list": grid_list,
                    },
                "payment_options": payment_options
        }

        return Response(resp)
