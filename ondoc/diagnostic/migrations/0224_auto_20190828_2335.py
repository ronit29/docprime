# Generated by Django 2.0.5 on 2019-08-28 18:05

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0223_auto_20190828_1134'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ipdmedicinepagelead',
            name='phone_number',
            field=models.BigIntegerField(validators=[django.core.validators.MaxValueValidator(9999999999), django.core.validators.MinValueValidator(1000000000)]),
        ),
    ]
