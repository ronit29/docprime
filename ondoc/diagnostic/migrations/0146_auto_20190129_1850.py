# Generated by Django 2.0.5 on 2019-01-29 13:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0145_merge_20190108_1624'),
    ]

    operations = [
        migrations.AddField(
            model_name='availablelabtest',
            name='supplier_name',
            field=models.CharField(blank=True, default=None, max_length=40, null=True),
        ),
        migrations.AddField(
            model_name='availablelabtest',
            name='supplier_price',
            field=models.DecimalField(blank=True, decimal_places=2, default=None, max_digits=10, null=True),
        ),
    ]