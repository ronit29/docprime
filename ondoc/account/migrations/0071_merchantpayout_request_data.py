# Generated by Django 2.0.5 on 2019-04-25 09:34

import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0070_merchantpayout_booking_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='merchantpayout',
            name='request_data',
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, default='', editable=False),
        ),
    ]
