# Generated by Django 2.0.5 on 2018-09-04 09:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0100_doctorclinictiming_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='doctor',
            name='live_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='doctor',
            name='onboarded_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
