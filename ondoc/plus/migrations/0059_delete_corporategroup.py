# Generated by Django 2.0.5 on 2020-01-16 13:09

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('plus', '0058_remove_plusplans_corporate_group'),
    ]

    operations = [
        migrations.DeleteModel(
            name='CorporateGroup',
        ),
    ]
