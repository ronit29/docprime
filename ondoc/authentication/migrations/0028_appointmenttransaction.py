# Generated by Django 2.0.5 on 2018-06-04 09:15

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0043_merge_20180604_1029'),
        ('authentication', '0027_merge_20180604_1029'),
    ]

    operations = [
        migrations.CreateModel(
            name='AppointmentTransaction',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('transaction_time', models.DateTimeField()),
                ('transaction_status', models.CharField(max_length=100)),
                ('status_code', models.PositiveIntegerField()),
                ('transaction_details', django.contrib.postgres.fields.jsonb.JSONField()),
                ('appointment', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='doctor.OpdAppointment')),
            ],
            options={
                'db_table': 'appointment_transaction',
            },
        ),
    ]
