# Generated by Django 2.0.5 on 2019-03-27 07:09

import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0230_merge_20190320_1712'),
    ]

    operations = [
        migrations.AddField(
            model_name='doctor',
            name='rating_data',
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True),
        ),
    ]
