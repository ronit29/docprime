# Generated by Django 2.0.5 on 2018-11-27 12:59

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0164_auto_20181127_1753'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='opdappointment',
            name='ratings',
        ),
    ]