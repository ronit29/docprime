# Generated by Django 2.0.5 on 2019-04-29 15:06

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('prescription', '0005_auto_20190429_1910'),
    ]

    operations = [
        migrations.CreateModel(
            name='PrescriptionHistory',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('data', django.contrib.postgres.fields.jsonb.JSONField()),
            ],
            options={
                'db_table': 'eprescription_history',
            },
        ),
    ]
