# Generated by Django 2.0.5 on 2018-11-27 12:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0163_hospital_ratings'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='hospital',
            name='ratings',
        ),
        migrations.AddField(
            model_name='opdappointment',
            name='ratings',
            field=models.PositiveIntegerField(null=True),
        ),
    ]
