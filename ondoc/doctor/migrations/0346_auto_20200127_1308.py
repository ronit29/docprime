# Generated by Django 2.0.5 on 2020-01-27 07:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0345_auto_20200121_1353'),
    ]

    operations = [
        migrations.AddField(
            model_name='searchscoreparams',
            name='max_value',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='searchscoreparams',
            name='min_value',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='searchscoreparams',
            name='score',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]