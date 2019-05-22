# Generated by Django 2.0.5 on 2019-05-22 05:33

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('procedure', '0051_auto_20190522_0953'),
    ]

    operations = [
        migrations.AddField(
            model_name='ipdprocedurelead',
            name='comments',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='ipdprocedurelead',
            name='data',
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True),
        ),
    ]
