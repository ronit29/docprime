# Generated by Django 2.0.2 on 2018-06-22 15:58

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0045_availablelabtest_enabled'),
    ]

    operations = [
        migrations.RenameField(
            model_name='availablelabtest',
            old_name='agreed_price',
            new_name='computed_agreed_price',
        ),
        migrations.RenameField(
            model_name='availablelabtest',
            old_name='deal_price',
            new_name='computed_deal_price',
        ),
        migrations.RenameField(
            model_name='lab',
            old_name='pathology_agreed_price_percent',
            new_name='pathology_agreed_price_percentage',
        ),
        migrations.RenameField(
            model_name='lab',
            old_name='pathology_deal_price_percent',
            new_name='pathology_deal_price_percentage',
        ),
        migrations.RenameField(
            model_name='lab',
            old_name='radiology_agreed_price_percent',
            new_name='radiology_agreed_price_percentage',
        ),
        migrations.RenameField(
            model_name='lab',
            old_name='radiology_deal_price_percent',
            new_name='radiology_deal_price_percentage',
        ),
    ]
