# Generated by Django 2.0.5 on 2018-12-03 08:31

from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('doctor', '0169_merge_20181129_1830'),
    ]

    operations = [
        migrations.CreateModel(
            name='OfflineOPDAppointments',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('fees', models.DecimalField(decimal_places=2, max_digits=10)),
                ('effective_price', models.DecimalField(decimal_places=2, default=None, max_digits=10)),
                ('mrp', models.DecimalField(decimal_places=2, default=None, max_digits=10)),
                ('deal_price', models.DecimalField(decimal_places=2, default=None, max_digits=10)),
                ('status', models.PositiveSmallIntegerField(choices=[(1, 'Created'), (2, 'Booked'), (3, 'Rescheduled by Doctor'), (4, 'Rescheduled by patient'), (5, 'Accepted'), (6, 'Cancelled'), (7, 'Completed')], default=1)),
                ('time_slot_start', models.DateTimeField(blank=True, null=True)),
                ('time_slot_end', models.DateTimeField(blank=True, null=True)),
                ('booked_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='offline_booked_appointements', to=settings.AUTH_USER_MODEL)),
                ('doctor', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='offline_doctor_appointments', to='doctor.Doctor')),
                ('hospital', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='offline_hospital_appointments', to='doctor.Hospital')),
            ],
            options={
                'db_table': 'offline_opd_appointments',
            },
        ),
        migrations.CreateModel(
            name='OfflinePatients',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=32)),
                ('sms_notification', models.BooleanField(default=False)),
                ('gender', models.CharField(blank=True, choices=[('m', 'Male'), ('f', 'Female'), ('o', 'Other')], default=None, max_length=2, null=True)),
                ('dob', models.DateField(blank=True, null=True)),
                ('referred_by', models.PositiveSmallIntegerField(blank=True, choices=[(1, 'Docprime'), (2, 'Google'), (3, 'JustDial'), (4, 'Friends'), (5, 'Others')], null=True)),
                ('medical_history', models.CharField(blank=True, max_length=256, null=True)),
                ('welcome_message', models.CharField(blank=True, max_length=128, null=True)),
                ('display_welcome_message', models.BooleanField(default=False)),
            ],
            options={
                'db_table': 'offline_patients',
            },
        ),
        migrations.CreateModel(
            name='PatientMobile',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('phone_number', models.BigIntegerField(blank=True, null=True, validators=[django.core.validators.MaxValueValidator(9999999999), django.core.validators.MinValueValidator(6000000000)])),
                ('is_default', models.BooleanField(default=False, verbose_name='Default Number?')),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='patient_mobiles', to='doctor.OfflinePatients')),
            ],
            options={
                'db_table': 'patient_mobile',
            },
        ),
        migrations.AddField(
            model_name='offlineopdappointments',
            name='user',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='offline_patients_appointment', to='doctor.OfflinePatients'),
        ),
    ]