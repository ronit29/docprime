# Generated by Django 2.0.5 on 2019-03-26 13:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ratings_review', '0018_auto_20190314_1830'),
    ]

    operations = [
        migrations.AddField(
            model_name='ratingsreview',
            name='related_entity_id',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]