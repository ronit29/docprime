# Generated by Django 2.0.5 on 2018-10-26 19:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('location', '0037_auto_20181026_1730'),
    ]

    operations = [
        migrations.AddField(
            model_name='cityinventory',
            name='rank',
            field=models.PositiveIntegerField(default=0, null=True),
        ),
    ]
