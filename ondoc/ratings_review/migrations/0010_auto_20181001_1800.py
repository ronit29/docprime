# Generated by Django 2.0.5 on 2018-10-01 12:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ratings_review', '0009_auto_20181001_1649'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='reviewcompliments',
            name='doc_high_rating',
        ),
        migrations.RemoveField(
            model_name='reviewcompliments',
            name='doc_low_rating',
        ),
        migrations.RemoveField(
            model_name='reviewcompliments',
            name='lab_high_rating',
        ),
        migrations.RemoveField(
            model_name='reviewcompliments',
            name='lab_low_rating',
        ),
        migrations.AddField(
            model_name='ratingsreview',
            name='compliment',
            field=models.ManyToManyField(related_name='compliment_review', to='ratings_review.ReviewCompliments'),
        ),
        migrations.AddField(
            model_name='reviewcompliments',
            name='message',
            field=models.CharField(default=None, max_length=128),
        ),
        migrations.AddField(
            model_name='reviewcompliments',
            name='rating_level',
            field=models.PositiveSmallIntegerField(default=None, max_length=5),
        ),
        migrations.AddField(
            model_name='reviewcompliments',
            name='type',
            field=models.PositiveSmallIntegerField(blank=True, choices=[(1, 'Lab'), (2, 'Opd')], null=True),
        ),
    ]
