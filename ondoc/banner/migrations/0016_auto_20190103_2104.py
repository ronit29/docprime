# Generated by Django 2.0.5 on 2019-01-03 15:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('banner', '0015_auto_20190103_1339'),
    ]

    operations = [
        migrations.AlterField(
            model_name='banner',
            name='url',
            field=models.URLField(blank=True, max_length=1000, null=True),
        ),
    ]