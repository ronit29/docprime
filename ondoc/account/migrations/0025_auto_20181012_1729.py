# Generated by Django 2.0.5 on 2018-10-12 11:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0024_auto_20180906_1820'),
    ]

    operations = [
        migrations.AlterField(
            model_name='consumertransaction',
            name='product_id',
            field=models.SmallIntegerField(blank=True, choices=[(1, 'Doctor Appointment'), (2, 'LAB_PRODUCT_ID'), (3, 'INSURANCE_PRODUCT_ID')], null=True),
        ),
        migrations.AlterField(
            model_name='invoice',
            name='product_id',
            field=models.SmallIntegerField(choices=[(1, 'Doctor Appointment'), (2, 'LAB_PRODUCT_ID'), (3, 'INSURANCE_PRODUCT_ID')]),
        ),
        migrations.AlterField(
            model_name='order',
            name='action',
            field=models.PositiveSmallIntegerField(blank=True, choices=[('', 'Select'), (1, 'Opd Reschedule'), (2, 'Opd Create'), (4, 'Lab Create'), (3, 'Lab Reschedule'), (5, 'Insurance Create')], null=True),
        ),
        migrations.AlterField(
            model_name='order',
            name='product_id',
            field=models.SmallIntegerField(choices=[(1, 'Doctor Appointment'), (2, 'LAB_PRODUCT_ID'), (3, 'INSURANCE_PRODUCT_ID')]),
        ),
        migrations.AlterField(
            model_name='pgtransaction',
            name='product_id',
            field=models.SmallIntegerField(choices=[(1, 'Doctor Appointment'), (2, 'LAB_PRODUCT_ID'), (3, 'INSURANCE_PRODUCT_ID')]),
        ),
    ]
