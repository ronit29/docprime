# Generated by Django 2.0.5 on 2018-08-31 12:54

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('articles', '0013_article_header_image'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='articleimage',
            name='height',
        ),
        migrations.RemoveField(
            model_name='articleimage',
            name='width',
        ),
    ]
