# Generated by Django 2.0.5 on 2018-09-11 07:04

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0091_auto_20180911_1152'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='labtestpackage',
            unique_together={('package', 'lab_test')},
        ),
    ]
