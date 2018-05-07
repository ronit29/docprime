# Generated by Django 2.0.2 on 2018-05-07 07:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0023_auto_20180507_1209'),
    ]

    operations = [
        migrations.AddField(
            model_name='lab',
            name='is_insurance_enabled',
            field=models.BooleanField(default=False, verbose_name='Enabled for Insurance Customer'),
        ),
        migrations.AddField(
            model_name='lab',
            name='is_retail_enabled',
            field=models.BooleanField(default=False, verbose_name='Enabled for Retail Customer'),
        ),
    ]
