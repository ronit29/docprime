# Generated by Django 2.0.5 on 2018-12-21 10:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('articles', '0032_article_author'),
    ]

    operations = [
        migrations.AddField(
            model_name='article',
            name='heading_title',
            field=models.CharField(blank=True, max_length=500),
        ),
    ]