# Generated by Django 2.0.5 on 2018-10-16 10:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('insurance', '0020_insuredmembers_diabetes'),
    ]

    operations = [
        migrations.AddField(
            model_name='insuredmembers',
            name='heart_disease',
            field=models.NullBooleanField(),
        ),
        migrations.AddField(
            model_name='insuredmembers',
            name='liver_disease',
            field=models.NullBooleanField(),
        ),
    ]
