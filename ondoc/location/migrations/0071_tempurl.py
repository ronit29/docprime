# Generated by Django 2.0.5 on 2019-01-07 13:50

import django.contrib.gis.db.models.fields
import django.contrib.postgres.fields.jsonb
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('location', '0070_auto_20190104_1415'),
    ]

    operations = [
        migrations.CreateModel(
            name='TempURL',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('url', models.CharField(db_index=True, max_length=2000, null=True)),
                ('url_type', models.CharField(max_length=24, null=True)),
                ('entity_type', models.CharField(max_length=24, null=True)),
                ('search_slug', models.CharField(max_length=1000, null=True)),
                ('extras', django.contrib.postgres.fields.jsonb.JSONField()),
                ('entity_id', models.PositiveIntegerField(default=None, null=True)),
                ('is_valid', models.BooleanField(default=True)),
                ('count', models.IntegerField(default=0, max_length=30, null=True)),
                ('sitemap_identifier', models.CharField(max_length=28, null=True)),
                ('sequence', models.PositiveIntegerField(default=0)),
                ('locality_latitude', models.DecimalField(decimal_places=8, max_digits=10, null=True)),
                ('locality_longitude', models.DecimalField(decimal_places=8, max_digits=10, null=True)),
                ('sublocality_value', models.TextField(default='', null=True)),
                ('locality_value', models.TextField(default='', null=True)),
                ('sublocality_latitude', models.DecimalField(blank=True, decimal_places=8, max_digits=10, null=True)),
                ('sublocality_longitude', models.DecimalField(blank=True, decimal_places=8, max_digits=10, null=True)),
                ('locality_id', models.PositiveIntegerField(default=None, null=True)),
                ('sublocality_id', models.PositiveIntegerField(default=None, null=True)),
                ('specialization', models.TextField(default='', null=True)),
                ('specialization_id', models.PositiveIntegerField(default=None, null=True)),
                ('locality_location', django.contrib.gis.db.models.fields.PointField(blank=True, geography=True, null=True, srid=4326)),
                ('sublocality_location', django.contrib.gis.db.models.fields.PointField(blank=True, geography=True, null=True, srid=4326)),
                ('location', django.contrib.gis.db.models.fields.PointField(blank=True, geography=True, null=True, srid=4326)),
            ],
            options={
                'db_table': 'temp_url',
            },
        ),
    ]
