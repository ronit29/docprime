# Generated by Django 2.0.5 on 2019-11-21 08:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('coupon', '0040_auto_20191121_1241'),
    ]

    operations = [
        migrations.AlterField(
            model_name='coupon',
            name='type',
            field=models.IntegerField(choices=[('', 'Select'), (1, 'Doctor'), (2, 'Lab'), (3, 'All'), (4, 'SUBSCRIPTION_PLAN'), (5, 'Vip'), (6, 'Gold')]),
        ),
    ]
