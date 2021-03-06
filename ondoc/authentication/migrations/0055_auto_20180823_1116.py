# Generated by Django 2.0.5 on 2018-08-23 05:46

import django.contrib.gis.db.models.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0054_agenttoken'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='address',
            name='place_id',
        ),
        migrations.AddField(
            model_name='address',
            name='landmark_location',
            field=django.contrib.gis.db.models.fields.PointField(blank=True, geography=True, null=True, srid=4326),
        ),
        migrations.AddField(
            model_name='address',
            name='landmark_place_id',
            field=models.CharField(blank=True, max_length=300, null=True),
        ),
        migrations.AddField(
            model_name='address',
            name='locality_location',
            field=django.contrib.gis.db.models.fields.PointField(blank=True, geography=True, null=True, srid=4326),
        ),
        migrations.AddField(
            model_name='address',
            name='locality_place_id',
            field=models.CharField(blank=True, max_length=300, null=True),
        ),
    ]
