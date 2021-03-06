# Generated by Django 2.0.5 on 2018-06-21 21:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0041_auto_20180621_2129'),
    ]

    operations = [
        migrations.AddField(
            model_name='lab',
            name='pathology_agreed_price_percent',
            field=models.DecimalField(blank=True, decimal_places=2, default=None, max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name='lab',
            name='pathology_deal_price_percent',
            field=models.DecimalField(blank=True, decimal_places=2, default=None, max_digits=7, null=True),
        ),
    ]
