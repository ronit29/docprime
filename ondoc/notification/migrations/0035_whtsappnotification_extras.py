# Generated by Django 2.0.5 on 2019-05-15 11:43

import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('notification', '0034_auto_20190515_1340'),
    ]

    operations = [
        migrations.AddField(
            model_name='whtsappnotification',
            name='extras',
            field=django.contrib.postgres.fields.jsonb.JSONField(default={}),
        ),
    ]
