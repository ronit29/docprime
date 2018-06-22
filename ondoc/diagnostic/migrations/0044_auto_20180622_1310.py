# Generated by Django 2.0.5 on 2018-06-22 07:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0043_auto_20180622_1055'),
    ]

    operations = [
        migrations.AddField(
            model_name='availablelabtest',
            name='custom_agreed_price',
            field=models.DecimalField(blank=True, decimal_places=2, default=None, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='availablelabtest',
            name='custom_deal_price',
            field=models.DecimalField(blank=True, decimal_places=2, default=None, max_digits=10, null=True),
        ),
    ]
