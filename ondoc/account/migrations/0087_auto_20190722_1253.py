# Generated by Django 2.0.5 on 2019-07-22 07:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0086_paymentprocessstatus'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paymentprocessstatus',
            name='current_status',
            field=models.PositiveSmallIntegerField(choices=[(1, 'Initiated'), (2, 'Authorize'), (3, 'Success'), (4, 'Failure')], default=1, editable=False),
        ),
        migrations.AlterField(
            model_name='pgtransaction',
            name='transaction_id',
            field=models.CharField(max_length=100, null=True, unique=True),
        ),
    ]
