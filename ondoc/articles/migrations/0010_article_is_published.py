# Generated by Django 2.0.5 on 2018-08-02 14:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('articles', '0009_auto_20180719_1453'),
    ]

    operations = [
        migrations.AddField(
            model_name='article',
            name='is_published',
            field=models.BooleanField(default=False, verbose_name='Published'),
        ),
    ]
