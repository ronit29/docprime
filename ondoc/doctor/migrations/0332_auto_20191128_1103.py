# Generated by Django 2.0.5 on 2019-11-28 05:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0331_auto_20191128_1053'),
    ]

    operations = [
        migrations.AlterField(
            model_name='googlemaprecords',
            name='combined_rating',
            field=models.FloatField(blank=True, null=True),
        ),
    ]
