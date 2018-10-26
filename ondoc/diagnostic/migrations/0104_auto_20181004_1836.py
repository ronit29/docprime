# Generated by Django 2.0.5 on 2018-10-04 13:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('coupon', '0001_initial'),
        ('diagnostic', '0103_labappointment_coupon'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='labappointment',
            name='coupon',
        ),
        migrations.AddField(
            model_name='labappointment',
            name='coupon',
            field=models.ManyToManyField(blank=True, null=True, to='coupon.Coupon'),
        ),
    ]
