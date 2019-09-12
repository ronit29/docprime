from django.core.management.base import BaseCommand

from ondoc.diagnostic.models import Lab, LabTestGroupMapping, LabTestGroupTiming, LabTestGroup, LabTest


def update_lab_test_group_timing():
    labs = Lab.objects.prefetch_related('lab_pricing_group', 'lab_pricing_group__available_lab_tests', 'lab_pricing_group__available_lab_tests__test', 'test_group_timings', 'lab_timings').all()
    for lab in labs:
        if lab.lab_pricing_group and lab.lab_pricing_group.available_lab_tests.all():
            available_lab_tests = lab.lab_pricing_group.available_lab_tests.filter(test__test_type=LabTest.RADIOLOGY)
            for data in available_lab_tests:
                labtest_group_mapping = LabTestGroupMapping.objects.filter(test=data.test).first()
                if labtest_group_mapping:
                    lab_test_group_timing = lab.test_group_timings.filter(lab_test_group=labtest_group_mapping.lab_test_group).exists()
                    if not lab_test_group_timing:
                        labs_list = list()
                        lab_timings = lab.lab_timings.all()
                        for timing in lab_timings:
                            labs_list.append(LabTestGroupTiming(lab=lab, lab_test_group=labtest_group_mapping.lab_test_group, day=timing.day, start=timing.start, end=timing.end,
                                                                for_home_pickup=False))
                        bulk_created = LabTestGroupTiming.objects.bulk_create(labs_list)

    # bulk_created = LabTestGroupTiming.objects.bulk_create(labs_list)
    print("success")
    return True


class Command(BaseCommand):
    def handle(self, **options):
        update_lab_test_group_timing()
