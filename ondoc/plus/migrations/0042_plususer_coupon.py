# Generated by Django 2.0.5 on 2019-11-21 11:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('coupon', '0042_coupon_vip_gold_plans'),
        ('plus', '0041_auto_20191111_1152'),
    ]

    operations = [
        migrations.AddField(
            model_name='plususer',
            name='coupon',
            field=models.ManyToManyField(blank=True, null=True, related_name='plus_coupon', to='coupon.Coupon'),
        ),
    ]