# Generated by Django 2.0.5 on 2018-09-17 12:57

from django.db import migrations, models
import django.utils.datetime_safe


class Migration(migrations.Migration):

    dependencies = [
        ('location', '0019_auto_20180917_1708'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='entityurlsrelation',
            name='content_type',
        ),
        migrations.RemoveField(
            model_name='entityurlsrelation',
            name='url',
        ),
        migrations.AddField(
            model_name='entityaddress',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.datetime_safe.datetime.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='entityaddress',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name='entitylocationrelationship',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.datetime_safe.datetime.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='entitylocationrelationship',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name='entityurls',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.datetime_safe.datetime.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='entityurls',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name='geoipresults',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.datetime_safe.datetime.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='geoipresults',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.DeleteModel(
            name='EntityUrlsRelation',
        ),
    ]