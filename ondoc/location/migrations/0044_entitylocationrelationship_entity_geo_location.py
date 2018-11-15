# Generated by Django 2.0.5 on 2018-11-13 07:37

import django.contrib.gis.db.models.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('location', '0043_entityurls_location'),
    ]

    operations = [
        migrations.AddField(
            model_name='entitylocationrelationship',
            name='entity_geo_location',
            field=django.contrib.gis.db.models.fields.PointField(blank=True, geography=True, null=True, srid=4326),
        ),
    ]
