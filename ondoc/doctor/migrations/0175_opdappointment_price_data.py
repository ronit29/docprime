# Generated by Django 2.0.5 on 2018-12-26 09:33

import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0174_remove_opdappointment_cashback_processed'),
    ]

    operations = [
        migrations.AddField(
            model_name='opdappointment',
            name='price_data',
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True),
        ),
    ]
