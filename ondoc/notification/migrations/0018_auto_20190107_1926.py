# Generated by Django 2.0.5 on 2019-01-07 13:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notification', '0017_merge_20190107_1923'),
    ]

    operations = [
        migrations.AlterField(
            model_name='appnotification',
            name='notification_type',
            field=models.PositiveIntegerField(choices=[(1, 'Appointment Accepted'), (2, 'Appointment Cancelled'), (3, 'Appointment Rescheduled by Patient'), (4, 'Appointment Rescheduled by Doctor'), (5, 'Appointment Booked'), (20, 'Lab Appointment Accepted'), (21, 'Lab Appointment Cancelled'), (22, 'Lab Appointment Rescheduled by Patient'), (23, 'Lab Appointment Rescheduled by Lab'), (24, 'Lab Appointment Booked'), (25, 'Lab Report Uploaded'), (26, 'Send Lab Reports via CRM'), (6, 'Prescription Uploaded'), (7, 'Payment Pending'), (8, 'Receipt'), (10, 'Doctor Invoice'), (11, 'Lab Invoice'), (15, 'Insurance Confirmed')]),
        ),
        migrations.AlterField(
            model_name='emailnotification',
            name='notification_type',
            field=models.PositiveIntegerField(choices=[(1, 'Appointment Accepted'), (2, 'Appointment Cancelled'), (3, 'Appointment Rescheduled by Patient'), (4, 'Appointment Rescheduled by Doctor'), (5, 'Appointment Booked'), (20, 'Lab Appointment Accepted'), (21, 'Lab Appointment Cancelled'), (22, 'Lab Appointment Rescheduled by Patient'), (23, 'Lab Appointment Rescheduled by Lab'), (24, 'Lab Appointment Booked'), (25, 'Lab Report Uploaded'), (26, 'Send Lab Reports via CRM'), (6, 'Prescription Uploaded'), (7, 'Payment Pending'), (8, 'Receipt'), (10, 'Doctor Invoice'), (11, 'Lab Invoice'), (15, 'Insurance Confirmed')]),
        ),
        migrations.AlterField(
            model_name='pushnotification',
            name='notification_type',
            field=models.PositiveIntegerField(choices=[(1, 'Appointment Accepted'), (2, 'Appointment Cancelled'), (3, 'Appointment Rescheduled by Patient'), (4, 'Appointment Rescheduled by Doctor'), (5, 'Appointment Booked'), (20, 'Lab Appointment Accepted'), (21, 'Lab Appointment Cancelled'), (22, 'Lab Appointment Rescheduled by Patient'), (23, 'Lab Appointment Rescheduled by Lab'), (24, 'Lab Appointment Booked'), (25, 'Lab Report Uploaded'), (26, 'Send Lab Reports via CRM'), (6, 'Prescription Uploaded'), (7, 'Payment Pending'), (8, 'Receipt'), (10, 'Doctor Invoice'), (11, 'Lab Invoice'), (15, 'Insurance Confirmed')]),
        ),
        migrations.AlterField(
            model_name='smsnotification',
            name='notification_type',
            field=models.PositiveIntegerField(choices=[(1, 'Appointment Accepted'), (2, 'Appointment Cancelled'), (3, 'Appointment Rescheduled by Patient'), (4, 'Appointment Rescheduled by Doctor'), (5, 'Appointment Booked'), (20, 'Lab Appointment Accepted'), (21, 'Lab Appointment Cancelled'), (22, 'Lab Appointment Rescheduled by Patient'), (23, 'Lab Appointment Rescheduled by Lab'), (24, 'Lab Appointment Booked'), (25, 'Lab Report Uploaded'), (26, 'Send Lab Reports via CRM'), (6, 'Prescription Uploaded'), (7, 'Payment Pending'), (8, 'Receipt'), (10, 'Doctor Invoice'), (11, 'Lab Invoice'), (15, 'Insurance Confirmed')]),
        ),
    ]
