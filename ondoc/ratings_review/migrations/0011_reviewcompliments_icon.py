# Generated by Django 2.0.5 on 2018-10-11 14:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ratings_review', '0010_auto_20181001_1800'),
    ]

    operations = [
        migrations.AddField(
            model_name='reviewcompliments',
            name='icon',
            field=models.ImageField(blank=True, default='', null=True, upload_to='rating_compliments/icons'),
        ),
    ]
