# Generated by Django 2.0.5 on 2019-07-08 10:20

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0275_merge_20190625_1301'),
    ]

    operations = [
        migrations.AlterField(
            model_name='generalinvoiceitems',
            name='tax_percentage',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, validators=[django.core.validators.MinValueValidator(0)]),
        ),
        migrations.AlterField(
            model_name='partnersappinvoice',
            name='tax_percentage',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, validators=[django.core.validators.MinValueValidator(0)]),
        ),
    ]