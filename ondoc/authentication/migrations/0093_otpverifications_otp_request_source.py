# Generated by Django 2.0.5 on 2019-05-15 06:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0092_lastlogintimestamp'),
    ]

    operations = [
        migrations.AddField(
            model_name='otpverifications',
            name='otp_request_source',
            field=models.CharField(default=None, max_length=200, null=True),
        ),
    ]
