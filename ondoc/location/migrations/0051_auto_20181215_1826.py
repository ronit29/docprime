# Generated by Django 2.0.5 on 2018-12-15 12:56

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('location', '0050_entityaddress_full_name'),
    ]

    operations = [
        migrations.RenameField(
            model_name='entityaddress',
            old_name='full_name',
            new_name='address',
        ),
        migrations.AddField(
            model_name='entityaddress',
            name='components',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.TextField(), null=True, size=None),
        ),
    ]
