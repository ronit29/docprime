# Generated by Django 2.0.5 on 2019-01-08 10:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0175_opdappointment_price_data'),
    ]

    operations = [
        migrations.AddField(
            model_name='hospital',
            name='pyhsical_aggrement_signed',
            field=models.BooleanField(default=False),
        ),
    ]