# Generated by Django 2.0.5 on 2019-02-18 07:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0200_hospital_is_mask_number_required'),
        ('coupon', '0023_auto_20190129_1449'),
    ]

    operations = [
        migrations.AddField(
            model_name='coupon',
            name='doctors',
            field=models.ManyToManyField(blank=True, to='doctor.Doctor'),
        ),
        migrations.AddField(
            model_name='coupon',
            name='hospitals',
            field=models.ManyToManyField(blank=True, to='doctor.Hospital'),
        ),
    ]
