# Generated by Django 2.0.5 on 2019-07-16 09:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0105_userprofileemailupdate'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofileemailupdate',
            name='otp_verified',
            field=models.BooleanField(),
        ),
    ]