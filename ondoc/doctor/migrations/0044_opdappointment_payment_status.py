# Generated by Django 2.0.5 on 2018-06-05 05:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0043_merge_20180604_1029'),
    ]

    operations = [
        migrations.AddField(
            model_name='opdappointment',
            name='payment_status',
            field=models.PositiveSmallIntegerField(choices=[(1, 'Payment Accepted'), (0, 'Payment Pending')], default=0),
        ),
    ]
