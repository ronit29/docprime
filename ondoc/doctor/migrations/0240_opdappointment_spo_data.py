# Generated by Django 2.0.5 on 2019-04-05 07:20

import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0239_auto_20190404_2028'),
    ]

    operations = [
        migrations.AddField(
            model_name='opdappointment',
            name='spo_data',
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True),
        ),
    ]