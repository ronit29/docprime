# Generated by Django 2.0.5 on 2018-11-05 14:10

import django.contrib.gis.db.models.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('location', '0042_auto_20181031_1140'),
    ]

    operations = [
        migrations.AddField(
            model_name='entityurls',
            name='location',
            field=django.contrib.gis.db.models.fields.PointField(blank=True, geography=True, null=True, srid=4326),
        ),
    ]
