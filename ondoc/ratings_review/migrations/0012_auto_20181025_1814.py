# Generated by Django 2.0.5 on 2018-10-25 12:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ratings_review', '0011_reviewcompliments_icon'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ratingsreview',
            name='review',
            field=models.CharField(blank=True, max_length=5000, null=True),
        ),
    ]
