# Generated by Django 2.0.5 on 2019-10-18 11:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0230_merge_20190924_1212'),
    ]

    operations = [
        migrations.AddField(
            model_name='lab',
            name='search_url_locality_radius',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='lab',
            name='search_url_sublocality_radius',
            field=models.FloatField(blank=True, null=True),
        ),
    ]
