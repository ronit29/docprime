# Generated by Django 2.0.2 on 2018-04-28 08:26

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0015_lab_agrees_rate'),
    ]

    operations = [
        migrations.RenameField(
            model_name='lab',
            old_name='agrees_rate',
            new_name='agreed_rate_list',
        ),
    ]
