# Generated by Django 2.0.4 on 2018-04-26 12:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0002_userprofile'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='userprofile',
            name='age',
        ),
        migrations.RemoveField(
            model_name='userprofile',
            name='isDefaultUser',
        ),
        migrations.RemoveField(
            model_name='userprofile',
            name='isOtpVerified',
        ),
        migrations.AddField(
            model_name='userprofile',
            name='dob',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='is_default_user',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='is_otp_verified',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='userprofile',
            name='email',
            field=models.CharField(default=None, max_length=20),
        ),
        migrations.AlterField(
            model_name='userprofile',
            name='name',
            field=models.CharField(default=None, max_length=100),
        ),
    ]
