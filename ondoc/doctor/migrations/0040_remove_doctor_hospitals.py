# Generated by Django 2.0.5 on 2018-05-28 13:01

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0039_merge_20180525_2024'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='doctor',
            name='hospitals',
        ),
    ]
