# Generated by Django 2.0.5 on 2018-06-08 11:01

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0046_doctorimage_cropped_image'),
    ]

    operations = [
        migrations.RenameField(
            model_name='prescriptionfile',
            old_name='file',
            new_name='name',
        ),
    ]