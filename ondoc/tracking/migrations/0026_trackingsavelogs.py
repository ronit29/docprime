# Generated by Django 2.0.5 on 2019-05-21 10:04

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracking', '0025_merge_20190319_1411'),
    ]

    operations = [
        migrations.CreateModel(
            name='TrackingSaveLogs',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('data', django.contrib.postgres.fields.jsonb.JSONField(null=True)),
            ],
            options={
                'db_table': 'tracking_logs',
            },
        ),
    ]
