# Generated by Django 2.0.5 on 2019-05-10 12:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('insurance', '0112_insurancedummydata_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='insuredmembers',
            name='city_code',
            field=models.IntegerField(default=None, null=True),
        ),
        migrations.AddField(
            model_name='insuredmembers',
            name='district_code',
            field=models.IntegerField(default=None, null=True),
        ),
    ]
