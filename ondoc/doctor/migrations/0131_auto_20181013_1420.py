# Generated by Django 2.0.5 on 2018-10-13 08:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0130_auto_20181013_1405'),
    ]

    operations = [
        migrations.AddField(
            model_name='doctor',
            name='batch',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name='hospital',
            name='batch',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name='hospital',
            name='source',
            field=models.CharField(blank=True, max_length=20),
        ),
    ]
