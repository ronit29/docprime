# Generated by Django 2.0.5 on 2019-01-02 06:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0046_auto_20190102_0939'),
    ]

    operations = [
        migrations.AlterField(
            model_name='consumertransaction',
            name='action',
            field=models.SmallIntegerField(choices=[(0, 'Cancellation'), (1, 'Payment'), (2, 'Refund'), (3, 'Sale'), (4, 'CashbackCredit'), (5, 'ReferralCredit')]),
        ),
    ]
