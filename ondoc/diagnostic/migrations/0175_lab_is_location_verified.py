# Generated by Django 2.0.5 on 2019-04-01 07:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0174_lab_rating_data'),
    ]

    operations = [
        migrations.AddField(
            model_name='lab',
            name='is_location_verified',
            field=models.BooleanField(default=False, verbose_name='Location Verified'),
        ),
    ]