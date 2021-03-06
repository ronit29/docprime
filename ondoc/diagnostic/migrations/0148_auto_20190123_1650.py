# Generated by Django 2.0.5 on 2019-01-23 11:20

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0147_auto_20190123_1646'),
    ]

    operations = [
        migrations.AlterField(
            model_name='labtest',
            name='max_age',
            field=models.PositiveSmallIntegerField(blank=True, default=None, null=True, validators=[django.core.validators.MaxValueValidator(120), django.core.validators.MinValueValidator(1)]),
        ),
        migrations.AlterField(
            model_name='labtest',
            name='min_age',
            field=models.PositiveSmallIntegerField(blank=True, default=None, null=True, validators=[django.core.validators.MaxValueValidator(120), django.core.validators.MinValueValidator(1)]),
        ),
    ]
