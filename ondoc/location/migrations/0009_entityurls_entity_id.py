# Generated by Django 2.0.5 on 2018-09-11 11:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('location', '0008_auto_20180911_1356'),
    ]

    operations = [
        migrations.AddField(
            model_name='entityurls',
            name='entity_id',
            field=models.PositiveIntegerField(default=None, null=True),
        ),
    ]
