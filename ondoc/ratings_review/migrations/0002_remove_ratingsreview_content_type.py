# Generated by Django 2.0.5 on 2018-09-25 09:40

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ratings_review', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='ratingsreview',
            name='content_type',
        ),
    ]
