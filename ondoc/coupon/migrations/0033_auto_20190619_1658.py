# Generated by Django 2.0.5 on 2019-06-19 11:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('coupon', '0032_merge_20190516_1820'),
    ]

    operations = [
        migrations.AddField(
            model_name='coupon',
            name='is_for_insurance',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='coupon',
            name='max_order_amount',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
    ]
