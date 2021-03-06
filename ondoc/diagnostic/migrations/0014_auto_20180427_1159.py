# Generated by Django 2.0.2 on 2018-04-27 06:29

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0013_auto_20180426_1939'),
    ]

    operations = [
        migrations.AddField(
            model_name='lab',
            name='onboarding_status',
            field=models.PositiveSmallIntegerField(choices=[(1, 'Not Onboarded'), (2, 'Onboarding Request Sent'), (3, 'Onboarded')], default=1),
        ),
        migrations.AddField(
            model_name='labonboardingtoken',
            name='email',
            field=models.EmailField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='labonboardingtoken',
            name='mobile',
            field=models.BigIntegerField(blank=True, null=True, validators=[django.core.validators.MaxValueValidator(9999999999), django.core.validators.MinValueValidator(1000000000)]),
        ),
    ]
