# Generated by Django 2.0.5 on 2018-12-20 08:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('lead', '0009_auto_20181220_1344'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userlead',
            name='gender',
            field=models.CharField(blank=True, choices=[('', 'Select'), ('m', 'Male'), ('f', 'Female'), ('o', 'Other')], default=None, max_length=2, null=True),
        ),
    ]
