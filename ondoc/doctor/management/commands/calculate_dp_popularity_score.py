from django.core.management.base import BaseCommand
from ondoc.doctor.services import update_search_score


def calculate_dp_popularity_score():
    obj = update_search_score.DoctorSearchScore()
    print(obj.calculate())


class Command(BaseCommand):
    def handle(self, **options):
        calculate_dp_popularity_score()
