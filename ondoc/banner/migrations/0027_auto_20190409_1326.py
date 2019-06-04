# Generated by Django 2.0.5 on 2019-04-09 07:56

import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('banner', '0026_auto_20190329_1515'),
    ]

    operations = [
        migrations.AlterField(
            model_name='banner',
            name='url_params_excluded',
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, help_text='JSON format example: {"specialization_id": [3667, 4321], "test_ids": [87], "is_package": True, "Name": "Stringvalue"}', null=True),
        ),
        migrations.AlterField(
            model_name='banner',
            name='url_params_included',
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, help_text='JSON format example: {"specialization_id": [3667, 4321], "test_ids": [87], "is_package": True, "Name": "Stringvalue"}', null=True),
        ),
    ]