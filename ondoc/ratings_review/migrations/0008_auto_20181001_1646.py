# Generated by Django 2.0.5 on 2018-10-01 11:16

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ratings_review', '0007_auto_20181001_1243'),
    ]

    operations = [
        migrations.RenameField(
            model_name='ratingsreview',
            old_name='appoitnment_id',
            new_name='appointment_id',
        ),
    ]
