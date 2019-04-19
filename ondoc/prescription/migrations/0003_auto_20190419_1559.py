# Generated by Django 2.0.5 on 2019-04-19 10:29

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('prescription', '0002_presccriptionpdf_prescription_file'),
    ]

    operations = [
        migrations.RenameField(
            model_name='prescriptionmedicine',
            old_name='appointment',
            new_name='hospital',
        ),
        migrations.RenameField(
            model_name='prescriptionobservations',
            old_name='appointment',
            new_name='hospital',
        ),
        migrations.RenameField(
            model_name='prescriptionobservations',
            old_name='observation',
            new_name='name',
        ),
        migrations.RenameField(
            model_name='prescriptionsymptoms',
            old_name='appointment',
            new_name='hospital',
        ),
        migrations.RenameField(
            model_name='prescriptionsymptoms',
            old_name='symptoms',
            new_name='name',
        ),
        migrations.RenameField(
            model_name='prescriptiontests',
            old_name='appointment',
            new_name='hospital',
        ),
        migrations.RenameField(
            model_name='prescriptiontests',
            old_name='test',
            new_name='name',
        ),
    ]
