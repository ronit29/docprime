# Generated by Django 2.0.5 on 2019-04-16 07:38

import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0240_merge_20190412_2014'),
    ]

    operations = [
        migrations.AddField(
            model_name='opdappointment',
            name='auto_ivr_data',
            field=django.contrib.postgres.fields.jsonb.JSONField(default=[]),
        ),
    ]
