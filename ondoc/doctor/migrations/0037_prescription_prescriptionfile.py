# Generated by Django 2.0.5 on 2018-05-12 05:18

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0036_doctorleave_deleted_at'),
    ]

    operations = [
        migrations.CreateModel(
            name='Prescription',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('prescription_details', models.TextField(blank=True, max_length=300, null=True)),
                ('appointment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.OpdAppointment')),
            ],
            options={
                'db_table': 'prescription',
            },
        ),
        migrations.CreateModel(
            name='PrescriptionFile',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('file', models.FileField(upload_to='prescriptions')),
                ('prescription', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.Prescription')),
            ],
            options={
                'db_table': 'prescription_file',
            },
        ),
    ]
