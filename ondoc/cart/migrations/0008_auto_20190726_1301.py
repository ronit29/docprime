# Generated by Django 2.0.5 on 2019-07-26 07:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cart', '0007_auto_20190326_1349'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cart',
            name='product_id',
            field=models.IntegerField(choices=[(1, 'Doctor Appointment'), (2, 'LAB_PRODUCT_ID'), (3, 'INSURANCE_PRODUCT_ID'), (4, 'SUBSCRIPTION_PLAN_PRODUCT_ID'), (5, 'CHAT_PRODUCT_ID')]),
        ),
    ]
