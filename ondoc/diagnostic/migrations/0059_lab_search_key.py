# Generated by Django 2.0.5 on 2018-07-11 10:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0058_merge_20180706_2117'),
    ]

    operations = [
        migrations.AddField(
            model_name='lab',
            name='search_key',
            field=models.CharField(blank=True, max_length=256, null=True),
        ),
    ]