# Generated by Django 2.0.5 on 2019-01-17 11:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0051_auto_20190117_1649'),
    ]

    operations = [
        migrations.AlterField(
            model_name='merchantpayout',
            name='amount_paid',
            field=models.DecimalField(blank=True, decimal_places=2, default=None, max_digits=10, null=True),
        ),
    ]
