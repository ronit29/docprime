# Generated by Django 2.0.5 on 2018-09-06 07:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('articles', '0016_article_header_image_alt'),
    ]

    operations = [
        migrations.AlterField(
            model_name='article',
            name='description',
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
        migrations.AlterField(
            model_name='article',
            name='header_image',
            field=models.ImageField(blank=True, default='', null=True, upload_to='articles/header/images'),
        ),
        migrations.AlterField(
            model_name='article',
            name='keywords',
            field=models.CharField(blank=True, max_length=256, null=True),
        ),
    ]
