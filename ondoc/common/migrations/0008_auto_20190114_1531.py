# Generated by Django 2.0.5 on 2019-01-14 10:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0007_auto_20190114_1322'),
    ]

    operations = [
        migrations.AddField(
            model_name='userconfig',
            name='share_text',
            field=models.CharField(default='', max_length=500),
        ),
        migrations.AddField(
            model_name='userconfig',
            name='share_url',
            field=models.URLField(default='', max_length=1000),
        ),
        migrations.AlterField(
            model_name='userconfig',
            name='key',
            field=models.CharField(max_length=500, unique=True),
        ),
    ]
