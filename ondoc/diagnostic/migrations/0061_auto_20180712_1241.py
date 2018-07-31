# Generated by Django 2.0.5 on 2018-07-12 07:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0060_auto_20180711_2037'),
    ]

    operations = [
        migrations.AddField(
            model_name='labpricinggroup',
            name='pathology_agreed_price_percentage',
            field=models.DecimalField(blank=True, decimal_places=2, default=None, max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name='labpricinggroup',
            name='pathology_deal_price_percentage',
            field=models.DecimalField(blank=True, decimal_places=2, default=None, max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name='labpricinggroup',
            name='radiology_agreed_price_percentage',
            field=models.DecimalField(blank=True, decimal_places=2, default=None, max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name='labpricinggroup',
            name='radiology_deal_price_percentage',
            field=models.DecimalField(blank=True, decimal_places=2, default=None, max_digits=7, null=True),
        ),
    ]