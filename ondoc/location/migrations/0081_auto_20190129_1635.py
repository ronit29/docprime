# Generated by Django 2.0.5 on 2019-01-29 11:05

import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('location', '0080_merge_20190111_1820'),
    ]

    operations = [
        migrations.AlterField(
            model_name='entityurls',
            name='extras',
            field=django.contrib.postgres.fields.jsonb.JSONField(null=True),
        ),
    ]
