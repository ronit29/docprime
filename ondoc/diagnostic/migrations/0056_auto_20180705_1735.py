# Generated by Django 2.0.5 on 2018-07-05 12:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0055_auto_20180703_1437'),
    ]

    operations = [
        migrations.AddField(
            model_name='lab',
            name='matrix_lead_id',
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='lab',
            name='matrix_reference_id',
            field=models.BigIntegerField(blank=True, null=True),
        ),
    ]
