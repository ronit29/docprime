from django.core.management.base import BaseCommand
from ondoc.doctor import models


def calculate_dp_popularity_score():
    success = models.calculate_popularity_score()
    if success:
        print("Successfull")
    else:
        print("Failed")


class Command(BaseCommand):
    def handle(self, **options):
        calculate_dp_popularity_score()
