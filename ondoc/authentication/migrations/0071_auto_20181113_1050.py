# Generated by Django 2.0.5 on 2018-11-13 05:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0070_auto_20181113_1046'),
    ]

    operations = [
        migrations.AddField(
            model_name='genericlabadmin',
            name='source_type',
            field=models.PositiveSmallIntegerField(choices=[(1, 'CRM'), (2, 'App')], default=1, max_length=20),
        ),
        migrations.AlterField(
            model_name='genericadmin',
            name='source_type',
            field=models.PositiveSmallIntegerField(choices=[(1, 'CRM'), (2, 'App')], default=1, max_length=20),
        ),
    ]