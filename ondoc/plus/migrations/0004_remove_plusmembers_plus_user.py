# Generated by Django 2.0.5 on 2019-08-28 08:39

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('plus', '0003_merge_20190828_0949'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='plusmembers',
            name='plus_user',
        ),
    ]
