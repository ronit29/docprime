# Generated by Django 2.0.5 on 2019-03-18 08:37

import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0029_auto_20190315_0958'),
    ]

    operations = [
        migrations.AddField(
            model_name='qrcode',
            name='data',
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True),
        ),
    ]
