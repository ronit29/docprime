# Generated by Django 2.0.5 on 2018-10-22 06:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('insurance', '0022_merge_20181017_1444'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='insurancetransaction',
            name='order_id',
        ),
        migrations.AlterField(
            model_name='insurancetransaction',
            name='amount',
            field=models.DecimalField(decimal_places=2, max_digits=10, null=True),
        ),
    ]
