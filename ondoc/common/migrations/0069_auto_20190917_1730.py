# Generated by Django 2.0.5 on 2019-09-17 12:00

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0068_sponsorlistingspecialization_location'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='sponsorlistingspecialization',
            name='poc',
        ),
        migrations.RemoveField(
            model_name='sponsorlistingspecialization',
            name='specialization',
        ),
        migrations.DeleteModel(
            name='SponsorListingSpecialization',
        ),
    ]
