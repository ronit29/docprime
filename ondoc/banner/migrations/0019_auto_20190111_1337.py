# Generated by Django 2.0.5 on 2019-01-11 08:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('banner', '0018_auto_20190111_1311'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='banner',
            name='app_params',
        ),
        migrations.RemoveField(
            model_name='banner',
            name='app_screen',
        ),
        migrations.RemoveField(
            model_name='banner',
            name='show_in_app',
        ),
        migrations.AlterField(
            model_name='banner',
            name='url',
            field=models.URLField(blank=True, max_length=1000, null=True),
        ),
    ]