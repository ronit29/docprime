# Generated by Django 2.0.5 on 2018-06-08 08:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0045_opdappointment_ucc'),
    ]

    operations = [
        migrations.AddField(
            model_name='doctorimage',
            name='cropped_image',
            field=models.ImageField(blank=True, height_field='height', null=True, upload_to='doctor/cropped_images', width_field='width'),
        ),
    ]