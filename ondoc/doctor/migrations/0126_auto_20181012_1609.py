# Generated by Django 2.0.5 on 2018-10-12 10:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0125_opdappointment_is_license_verified'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='opdappointment',
            name='is_license_verified',
        ),
        migrations.AddField(
            model_name='doctor',
            name='is_license_verified',
            field=models.BooleanField(default=False),
        ),
    ]