# Generated by Django 2.0.2 on 2018-04-16 02:45

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0006_remove_doctor_awards'),
    ]

    operations = [
        migrations.AddField(
            model_name='doctoraward',
            name='year',
            field=models.PositiveSmallIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(1950)]),
        ),
    ]
