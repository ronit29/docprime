# Generated by Django 2.0.5 on 2018-06-13 07:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notification', '0002_auto_20180607_1621'),
    ]

    operations = [
        migrations.AlterField(
            model_name='appnotification',
            name='notification_type',
            field=models.PositiveIntegerField(choices=[(1, 'Appointment Accepted'), (2, 'Appointment Cancelled'), (3, 'Appointment Rescheduled by Patient'), (4, 'Appointment Rescheduled by Doctor'), (5, 'Appointment Booked')]),
        ),
        migrations.AlterField(
            model_name='emailnotification',
            name='notification_type',
            field=models.PositiveIntegerField(choices=[(1, 'Appointment Accepted'), (2, 'Appointment Cancelled'), (3, 'Appointment Rescheduled by Patient'), (4, 'Appointment Rescheduled by Doctor'), (5, 'Appointment Booked')]),
        ),
        migrations.AlterField(
            model_name='pushnotification',
            name='notification_type',
            field=models.PositiveIntegerField(choices=[(1, 'Appointment Accepted'), (2, 'Appointment Cancelled'), (3, 'Appointment Rescheduled by Patient'), (4, 'Appointment Rescheduled by Doctor'), (5, 'Appointment Booked')]),
        ),
        migrations.AlterField(
            model_name='smsnotification',
            name='notification_type',
            field=models.PositiveIntegerField(choices=[(1, 'Appointment Accepted'), (2, 'Appointment Cancelled'), (3, 'Appointment Rescheduled by Patient'), (4, 'Appointment Rescheduled by Doctor'), (5, 'Appointment Booked')]),
        ),
    ]
