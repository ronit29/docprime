# Generated by Django 2.0.5 on 2018-12-21 10:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('lead', '0011_auto_20181220_1355'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userlead',
            name='gender',
            field=models.CharField(blank=True, choices=[('', 'Select'), ('m', 'Male'), ('f', 'Female'), ('o', 'Other')], default='', max_length=2),
        ),
    ]
