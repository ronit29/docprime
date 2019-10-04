# Generated by Django 2.0.5 on 2019-10-01 09:49

from django.db import migrations
import multiselectfield.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ('banner', '0051_auto_20190930_1444'),
    ]

    operations = [
        migrations.AlterField(
            model_name='recommender',
            name='notification_type',
            field=multiselectfield.db.fields.MultiSelectField(blank=True, choices=[(1, 'Appointment Accepted'), (2, 'Appointment Cancelled'), (3, 'Appointment Rescheduled by Patient'), (4, 'Appointment Rescheduled by Doctor'), (5, 'Appointment Booked'), (20, 'Lab Appointment Accepted'), (21, 'Lab Appointment Cancelled'), (22, 'Lab Appointment Rescheduled by Patient'), (23, 'Lab Appointment Rescheduled by Lab'), (24, 'Lab Appointment Booked'), (25, 'Lab Report Uploaded'), (26, 'Send Lab Reports via CRM'), (130, 'Offline OPD Appointment Booked'), (131, 'Offline OPD Appointment Accepted'), (132, 'Offline OPD Appointment Cancelled'), (133, 'Offline OPD Appointment Rescheduled by Doctor'), (134, 'Offline OPD Appointment No Show'), (136, 'Offline OPD Appointment Completed'), (69, 'Docprime Appointment Reminder Provider SMS'), (137, 'Offline Appointment Reminder Provider SMS'), (150, 'EConsultation Booked'), (151, 'EConsultation Accepted'), (152, 'EConsultation Rescheduled Doctor'), (153, 'EConsultation Rescheduled Patient'), (154, 'EConsultation Cancelled'), (155, 'EConsultation Completed'), (156, 'EConsultation Expired'), (157, 'E Consult Share'), (158, 'E Consult Video Link Share'), (159, 'E Consult New Message Received'), (6, 'Prescription Uploaded'), (7, 'Payment Pending'), (8, 'Receipt'), (10, 'Doctor Invoice'), (11, 'Lab Invoice'), (135, 'Offline OPD Invoice'), (15, 'Insurance Confirmed'), (82, 'Insurance endorsment completed.'), (83, 'Insurance endorsment rejected.'), (84, 'Insurance endorsment received.'), (55, 'Cashback Credited'), (40, 'Refund break up'), (42, 'Refund Completed'), (60, 'IPD Procedure Mail'), (72, 'Pricing Change Mail'), (70, 'Lab Logo Change Mail'), (88, 'Provider Matrix Lead Email'), (69, 'Docprime Appointment Reminder Provider SMS'), (78, 'Provider Encryption Enabled'), (79, 'Provider Decryption Disabled'), (81, 'Request Encryption Key'), (80, 'Login OTP'), (87, 'Push Notification from chat'), (91, 'COD to Prepaid'), (92, 'COD To Prepaid Request'), (98, 'OPD Daily Schedule'), (200, 'Partner Lab Sample Extraction Pending'), (201, 'Partner Lab Sample Scan Pending'), (202, 'Partner Lab Sample Pickup Pending'), (203, 'Partner Lab Sample Picked Up'), (204, 'Partner Lab Partial Report Generated'), (205, 'Partner Lab Report Generated'), (206, 'Partner Lab Report Viewed'), (207, 'Partner Lab Request Recheck'), (208, 'Partner Lab Need Help'), (209, 'Partner Lab Report Uploaded'), (210, 'Partner Lab Order Placed Successfully'), (211, 'Partner Lab Report Success')], max_length=225, null=True),
        ),
    ]
