# Generated by Django 2.0.5 on 2018-12-26 09:33

import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0139_merge_20181226_1207'),
    ]

    operations = [
        migrations.AddField(
            model_name='labappointment',
            name='price_data',
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True),
        ),
    ]