# Generated by Django 2.0.5 on 2019-03-15 12:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0224_auto_20190314_1709'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cancellationreason',
            name='type',
            field=models.PositiveSmallIntegerField(blank=True, choices=[('', 'Both'), (1, 'Doctor Appointment'), (2, 'LAB_PRODUCT_ID'), (3, 'SUBSCRIPTION_PLAN_PRODUCT_ID')], default=None, null=True),
        ),
    ]