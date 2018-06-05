# Generated by Django 2.0.5 on 2018-06-05 05:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0033_merge_20180604_1029'),
    ]

    operations = [
        migrations.AddField(
            model_name='labappointment',
            name='payment_status',
            field=models.PositiveIntegerField(choices=[(1, 'Payment Accepted'), (0, 'Payment Pending')], default=0),
        ),
        migrations.AddField(
            model_name='labappointment',
            name='ucc',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
