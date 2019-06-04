# Generated by Django 2.0.5 on 2019-04-25 14:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0072_auto_20190425_1659'),
    ]

    operations = [
        migrations.AlterField(
            model_name='merchantpayout',
            name='booking_type',
            field=models.IntegerField(blank=True, choices=[(1, 'Doctor Booking'), (2, 'Lab Booking'), (3, 'Insurance Purchase')], null=True),
        ),
    ]