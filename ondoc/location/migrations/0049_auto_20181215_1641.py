# Generated by Django 2.0.5 on 2018-12-15 11:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('location', '0048_auto_20181214_2146'),
    ]

    operations = [
        migrations.AlterField(
            model_name='geocodingresults',
            name='latitude',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AlterField(
            model_name='geocodingresults',
            name='longitude',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
    ]
