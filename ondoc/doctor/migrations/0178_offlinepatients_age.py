# Generated by Django 2.0.5 on 2018-12-19 06:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0177_auto_20181218_1452'),
    ]

    operations = [
        migrations.AddField(
            model_name='offlinepatients',
            name='age',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]