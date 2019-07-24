# Generated by Django 2.0.5 on 2019-07-19 07:11

from django.db import migrations
import multiselectfield.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ('banner', '0041_merge_20190614_2117'),
    ]

    operations = [
        migrations.AlterField(
            model_name='recommender',
            name='notification_type',
            field=multiselectfield.db.fields.MultiSelectField(blank=True, choices=[(1, 'Appointment Accepted'), (2, 'Appointment Cancelled'), (3, 'Appointment Rescheduled by Patient'), (4, 'Appointment Rescheduled by Doctor'), (5, 'Appointment Booked'), (20, 'Lab Appointment Accepted'), (21, 'Lab Appointment Cancelled'), (22, 'Lab Appointment Rescheduled by Patient'), (23, 'Lab Appointment Rescheduled by Lab'), (24, 'Lab Appointment Booked'), (25, 'Lab Report Uploaded'), (26, 'Send Lab Reports via CRM'), (6, 'Prescription Uploaded'), (7, 'Payment Pending'), (8, 'Receipt'), (10, 'Doctor Invoice'), (11, 'Lab Invoice'), (15, 'Insurance Confirmed'), (82, 'Insurance endorsment completed.'), (83, 'Insurance endorsment rejected.'), (84, 'Insurance endorsment received.'), (55, 'Cashback Credited'), (40, 'Refund break up'), (42, 'Refund Completed'), (60, 'IPD Procedure Mail'), (72, 'Pricing Change Mail'), (70, 'Lab Logo Change Mail'), (69, 'Docprime Appointment Reminder Provider SMS'), (77, 'Offline Appointment Reminder Provider SMS'), (80, 'Login OTP'), (87, 'Push Notification from chat'), (91, 'COD to Prepaid'), (92, 'COD To Prepaid Request'), (99, 'OPD Daily Schedule')], max_length=93, null=True),
        ),
    ]
