# Generated by Django 2.0.5 on 2018-12-17 12:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('banner', '0009_auto_20181217_1306'),
    ]

    operations = [
        migrations.AlterField(
            model_name='banner',
            name='url',
            field=models.URLField(blank=True, max_length=1000),
        ),
    ]
