# Generated by Django 2.0.5 on 2019-03-13 07:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0221_merge_20190312_0914'),
    ]

    operations = [
        migrations.AddField(
            model_name='hospital',
            name='city_search_key',
            field=models.CharField(blank=True, default='', max_length=100, null=True),
        ),
    ]
