# Generated by Django 2.0.2 on 2018-04-15 07:23

import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0004_hospital_network_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='doctor',
            name='awards',
            field=django.contrib.postgres.fields.jsonb.JSONField(default=list),
        ),
    ]
