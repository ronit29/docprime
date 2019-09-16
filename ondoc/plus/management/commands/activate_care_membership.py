from django.core.management.base import BaseCommand
from ondoc.plus.models import PlusUser
from ondoc.subscription_plan.models import UserPlanMapping
from django.conf import settings


def activate_care():
    print("Activating care membership for all plus users who have not been activated.")
    plus_users = PlusUser.objects.all()
    for plus_user in plus_users:
        user = plus_user.user
        if not UserPlanMapping.objects.filter(user=user).exists():
            plus_user.activate_care_membership()
            print("Successfully purchased care membership for plus_user id %s" % str(plus_user.id))


class Command(BaseCommand):

    def handle(self, **options):
        activate_care()
