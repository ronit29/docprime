# Generated by Django 2.0.5 on 2019-07-15 10:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0215_auto_20190709_1607'),
    ]

    operations = [
        migrations.AddField(
            model_name='labtestcategoryurls',
            name='latitude',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='labtestcategoryurls',
            name='longitude',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='labtestcategoryurls',
            name='radius',
            field=models.FloatField(blank=True, null=True),
        ),
    ]
