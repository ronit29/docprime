# Generated by Django 2.0.5 on 2018-10-09 11:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('location', '0028_auto_20181009_1515'),
    ]

    operations = [
        migrations.AddField(
            model_name='entityurls',
            name='sequence',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
