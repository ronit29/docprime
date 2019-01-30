# Generated by Django 2.0.5 on 2018-12-06 12:02

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0172_offlinepatients_created_by'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='offlineopdappointments',
            name='booked_by',
        ),
        migrations.RemoveField(
            model_name='offlineopdappointments',
            name='doctor',
        ),
        migrations.RemoveField(
            model_name='offlineopdappointments',
            name='hospital',
        ),
        migrations.RemoveField(
            model_name='offlineopdappointments',
            name='user',
        ),
        migrations.RemoveField(
            model_name='offlinepatients',
            name='created_by',
        ),
        migrations.RemoveField(
            model_name='offlinepatients',
            name='doctor',
        ),
        migrations.RemoveField(
            model_name='offlinepatients',
            name='hospital',
        ),
        migrations.RemoveField(
            model_name='patientmobile',
            name='patient',
        ),
        migrations.DeleteModel(
            name='OfflineOPDAppointments',
        ),
        migrations.DeleteModel(
            name='OfflinePatients',
        ),
        migrations.DeleteModel(
            name='PatientMobile',
        ),
    ]