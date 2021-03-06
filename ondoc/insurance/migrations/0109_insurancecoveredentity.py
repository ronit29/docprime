# Generated by Django 2.0.5 on 2019-05-07 14:00

import django.contrib.gis.db.models.fields
import django.contrib.postgres.fields.jsonb
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('insurance', '0108_merge_20190503_1658'),
    ]

    operations = [
        migrations.CreateModel(
            name='InsuranceCoveredEntity',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('entity_id', models.PositiveIntegerField()),
                ('name', models.CharField(max_length=1000)),
                ('location', django.contrib.gis.db.models.fields.PointField(blank=True, geography=True, null=True, srid=4326)),
                ('type', models.CharField(max_length=50)),
                ('search_key', models.CharField(blank=True, max_length=1000, null=True)),
                ('data', django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True)),
            ],
            options={
                'db_table': 'insurance_covered_entity',
            },
        ),
    ]
