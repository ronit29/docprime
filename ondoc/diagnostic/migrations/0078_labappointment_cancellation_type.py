# Generated by Django 2.0.5 on 2018-08-17 08:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0077_labappointment_home_pickup_charges'),
    ]

    operations = [
        migrations.AddField(
            model_name='labappointment',
            name='cancellation_type',
            field=models.PositiveSmallIntegerField(blank=True, choices=[(1, 'Patient Cancelled'), (2, 'Agent Cancelled'), (3, 'Auto Cancelled')], null=True),
        ),
    ]