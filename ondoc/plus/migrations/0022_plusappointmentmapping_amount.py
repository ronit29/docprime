# Generated by Django 2.0.5 on 2019-09-11 13:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('plus', '0021_plusappointmentmapping'),
    ]

    operations = [
        migrations.AddField(
            model_name='plusappointmentmapping',
            name='amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
    ]
