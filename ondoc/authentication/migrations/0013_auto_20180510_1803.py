# Generated by Django 2.0.2 on 2018-05-10 12:33

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0012_auto_20180510_1628'),
    ]

    operations = [
        migrations.RenameField(
            model_name='otpverifications',
            old_name='isExpired',
            new_name='is_expired',
        ),
    ]
