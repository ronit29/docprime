# Generated by Django 2.0.5 on 2019-03-11 12:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0025_merge_20190304_1625'),
    ]

    operations = [
        migrations.AlterField(
            model_name='globalnonbookable',
            name='booking_type',
            field=models.CharField(choices=[('doctor', 'Doctor Clinic'), ('lab', 'Lab')], max_length=20),
        ),
    ]
