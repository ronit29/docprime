# Generated by Django 2.0.5 on 2019-01-11 07:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('banner', '0016_auto_20190103_2104'),
    ]

    operations = [
        migrations.AddField(
            model_name='banner',
            name='show_in_app',
            field=models.BooleanField(default=True),
        ),
    ]