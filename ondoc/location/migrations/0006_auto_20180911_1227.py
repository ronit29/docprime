# Generated by Django 2.0.5 on 2018-09-11 06:57

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('location', '0005_entityurls_url_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='entityurls',
            name='entity_type',
            field=models.CharField(max_length=24, null=True),
        ),
    ]
