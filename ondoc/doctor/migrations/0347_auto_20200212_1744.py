# Generated by Django 2.0.5 on 2020-02-12 12:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0346_auto_20200210_1812'),
    ]

    operations = [
        migrations.AlterField(
            model_name='googlemaprecords',
            name='samples_per_month',
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
    ]
