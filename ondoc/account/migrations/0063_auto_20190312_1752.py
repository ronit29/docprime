# Generated by Django 2.0.5 on 2019-03-12 12:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0062_merge_20190312_1254'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='product_id',
            field=models.SmallIntegerField(blank=True, choices=[(1, 'Doctor Appointment'), (2, 'LAB_PRODUCT_ID'), (3, 'INSURANCE_PRODUCT_ID')], null=True),
        ),
    ]
