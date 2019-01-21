# Generated by Django 2.0.5 on 2019-01-17 11:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0050_auto_20190117_1631'),
    ]

    operations = [
        migrations.AlterField(
            model_name='merchantpayout',
            name='amount_paid',
            field=models.DecimalField(blank=True, decimal_places=2, default=0, max_digits=10, null=True),
        ),
        migrations.AlterField(
            model_name='merchantpayout',
            name='type',
            field=models.PositiveIntegerField(blank=True, choices=[(1, 'Automatic'), (2, 'Manual')], default=None, null=True),
        ),
    ]