# Generated by Django 2.0.5 on 2019-08-27 11:12

import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0223_labappointmenttestmapping_is_home_pickup'),
    ]

    operations = [
        migrations.AddField(
            model_name='labappointment',
            name='action_data',
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True),
        ),
    ]
