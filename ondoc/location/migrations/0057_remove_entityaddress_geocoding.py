# Generated by Django 2.0.5 on 2018-12-17 16:53

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('location', '0056_auto_20181217_2223'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='entityaddress',
            name='geocoding',
        ),
    ]
