# Generated by Django 2.0.5 on 2019-11-28 06:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0332_auto_20191128_1103'),
    ]

    operations = [
        migrations.AlterField(
            model_name='googlemaprecords',
            name='phone_number',
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
    ]
