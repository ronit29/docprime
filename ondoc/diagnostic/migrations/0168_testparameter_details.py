# Generated by Django 2.0.5 on 2019-03-07 09:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0167_merge_20190304_1959'),
    ]

    operations = [
        migrations.AddField(
            model_name='testparameter',
            name='details',
            field=models.CharField(blank=True, max_length=10000, null=True),
        ),
    ]
