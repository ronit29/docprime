# Generated by Django 2.0.5 on 2019-04-29 07:02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0247_auto_20190425_1447'),
    ]

    operations = [
        migrations.AddField(
            model_name='searchscore',
            name='avg_ratings_score',
            field=models.PositiveIntegerField(default=None, null=True),
        ),
        migrations.AddField(
            model_name='searchscore',
            name='ratings_count_score',
            field=models.PositiveIntegerField(default=None, null=True),
        ),
    ]