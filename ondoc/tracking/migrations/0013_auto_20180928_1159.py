# Generated by Django 2.0.5 on 2018-09-28 06:29

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracking', '0012_serverhitmonitor_ip_address'),
    ]

    operations = [
        migrations.AddField(
            model_name='serverhitmonitor',
            name='agent',
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name='serverhitmonitor',
            name='navigator',
            field=django.contrib.postgres.fields.jsonb.JSONField(default={}),
            preserve_default=False,
        ),
    ]
