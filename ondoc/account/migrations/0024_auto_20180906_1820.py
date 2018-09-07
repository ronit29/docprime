# Generated by Django 2.0.5 on 2018-09-06 12:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0023_auto_20180906_1814'),
    ]

    operations = [
        migrations.AlterField(
            model_name='consumerrefund',
            name='refund_state',
            field=models.PositiveSmallIntegerField(choices=[(1, 'Pending'), (10, 'Completed'), (5, 'Requested')], default=1),
        ),
    ]
