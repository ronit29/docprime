# Generated by Django 2.0.5 on 2018-10-23 06:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0058_auto_20180829_1443'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='is_insured',
            field=models.BooleanField(default=False),
        ),
    ]
