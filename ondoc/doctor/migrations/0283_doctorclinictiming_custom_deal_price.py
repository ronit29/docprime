# Generated by Django 2.0.5 on 2019-07-25 11:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0282_doctorclinictiming_insurance_fees'),
    ]

    operations = [
        migrations.AddField(
            model_name='doctorclinictiming',
            name='custom_deal_price',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
    ]
