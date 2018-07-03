# Generated by Django 2.0.5 on 2018-06-21 15:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0040_auto_20180614_1308'),
    ]

    operations = [
        migrations.AlterField(
            model_name='availablelabtest',
            name='agreed_price',
            field=models.DecimalField(blank=True, decimal_places=2, default=None, max_digits=10, null=True),
        ),
        migrations.AlterField(
            model_name='availablelabtest',
            name='deal_price',
            field=models.DecimalField(blank=True, decimal_places=2, default=None, max_digits=10, null=True),
        ),
        migrations.AlterField(
            model_name='availablelabtest',
            name='mrp',
            field=models.DecimalField(blank=True, decimal_places=2, default=None, max_digits=10, null=True),
        ),
    ]