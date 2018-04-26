# Generated by Django 2.0.4 on 2018-04-26 12:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0003_auto_20180426_1805'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='height',
            field=models.PositiveSmallIntegerField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='profile_image',
            field=models.ImageField(blank=True, height_field='height', null=True, upload_to='user/images', width_field='width'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='width',
            field=models.PositiveSmallIntegerField(blank=True, editable=False, null=True),
        ),
    ]
