# Generated by Django 2.0.5 on 2018-07-06 06:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0059_auto_20180702_1849'),
    ]

    operations = [
        migrations.AddField(
            model_name='hospital',
            name='is_appointment_manager',
            field=models.BooleanField(default=False, verbose_name='Enabled for Managing Appointments'),
        ),
    ]
