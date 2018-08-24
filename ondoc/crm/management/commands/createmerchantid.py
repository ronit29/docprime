from django.core.management.base import BaseCommand
from ondoc.doctor import models as doc_models
from ondoc.authentication import models as auth_models
from ondoc.diagnostic import models as diag_models
from django.db import transaction


class Command(BaseCommand):

    help = 'Create default Appointment Admins'

    @transaction.atomic
    def handle(self, *args, **options):
        doctors = doc_models.Doctor.objects.all()
        for doc in doctors:
            if not doc.billing_merchant.exists():
                doc_billing_object = auth_models.BillingAccount(content_object=doc, enabled=True)
                doc_billing_object.save()
        hospitals = doc_models.Hospital.objects.all()
        for hos in hospitals:
            if not hos.billing_merchant.exists():
                hos_billing_object = auth_models.BillingAccount(content_object=hos, enabled=True)
                hos_billing_object.save()
        hospital_networks = doc_models.HospitalNetwork.objects.all()
        for hnet in hospital_networks:
            if not hnet.billing_merchant.exists():
                hnet_billing_object = auth_models.BillingAccount(content_object=hnet, enabled=True)
                hnet_billing_object.save()
        labs = diag_models.Lab.objects.all()
        for lab in labs:
            if not lab.billing_merchant.exists():
                lab_billing_object = auth_models.BillingAccount(content_object=lab, enabled=True)
                lab_billing_object.save()
        lab_networks = diag_models.LabNetwork.objects.all()
        for lnet in lab_networks:
            if not lnet.billing_merchant.exists():
                lnet_billing_object = auth_models.BillingAccount(content_object=lnet, enabled=True)
                lnet_billing_object.save()
        self.stdout.write('Successfully Created Merchant IDs')




