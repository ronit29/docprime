# Generated by Django 2.0.5 on 2019-03-13 05:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0218_merge_20190312_1254'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cancellationreason',
            name='type',
            field=models.PositiveSmallIntegerField(blank=True, choices=[('', 'Both'), (1, 'Doctor Appointment'), (2, 'LAB_PRODUCT_ID'), (3, 'INSURANCE_PRODUCT_ID')], default=None, null=True),
        ),
    ]
