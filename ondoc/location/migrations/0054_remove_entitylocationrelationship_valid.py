# Generated by Django 2.0.5 on 2018-12-17 08:31

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('location', '0053_entityaddress_search_slug'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='entitylocationrelationship',
            name='valid',
        ),
    ]
