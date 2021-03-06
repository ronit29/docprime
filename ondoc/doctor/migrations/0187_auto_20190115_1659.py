# Generated by Django 2.0.5 on 2019-01-15 11:29

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0186_merge_20190114_1046'),
    ]

    operations = [
        migrations.AlterField(
            model_name='uploaddoctordata',
            name='error_msg',
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name='uploaddoctordata',
            name='status',
            field=models.PositiveSmallIntegerField(choices=[('', 'Select'), (1, 'Created'), (2, 'Upload in progress'), (3, 'Upload successful'), (4, 'Upload Failed')], default=1, editable=False),
        ),
    ]
