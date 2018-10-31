# Generated by Django 2.0.5 on 2018-10-25 09:08

from decimal import Decimal
import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0108_auto_20181025_1252'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='lab',
            name='dayend_booking_threshold_hours',
        ),
        migrations.AddField(
            model_name='lab',
            name='booking_closing_hours_from_dayend',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10, validators=[django.core.validators.MinValueValidator(Decimal('0.00'))]),
        ),
    ]