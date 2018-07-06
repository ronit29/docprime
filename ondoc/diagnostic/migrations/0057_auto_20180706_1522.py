# Generated by Django 2.0.5 on 2018-07-06 09:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0056_auto_20180705_1735'),
    ]

    operations = [
        migrations.AddField(
            model_name='lab',
            name='home_pickup_charges',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name='lab',
            name='is_home_pickup_available',
            field=models.BigIntegerField(blank=True, null=True),
        ),
    ]
