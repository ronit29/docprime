# Generated by Django 2.0.5 on 2018-09-28 08:55

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('tracking', '0017_merge_20180928_1237'),
    ]

    operations = [
        migrations.RenameField(
            model_name='serverhitmonitor',
            old_name='navigator',
            new_name='data',
        ),
    ]
