# Generated by Django 2.0.5 on 2019-01-25 09:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0192_auto_20190125_1514'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cancellationreason',
            name='type',
            field=models.PositiveSmallIntegerField(blank=True, choices=[('', 'Select'), (1, 'Doctor Appointment'), (2, 'LAB_PRODUCT_ID')], default=None, null=True),
        ),
    ]
