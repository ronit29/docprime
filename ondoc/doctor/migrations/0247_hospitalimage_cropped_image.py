# Generated by Django 2.0.5 on 2019-05-02 06:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0246_practicespecialization_is_insurance_enabled'),
    ]

    operations = [
        migrations.AddField(
            model_name='hospitalimage',
            name='cropped_image',
            field=models.ImageField(blank=True, height_field='height', null=True, upload_to='hospital/images', width_field='width'),
        ),
    ]