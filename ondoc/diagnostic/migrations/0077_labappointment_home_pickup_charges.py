# Generated by Django 2.0.6 on 2018-08-14 08:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0076_remove_lab_is_home_pickup_available'),
    ]

    operations = [
        migrations.AddField(
            model_name='labappointment',
            name='home_pickup_charges',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
    ]
