# Generated by Django 2.0.5 on 2019-12-17 10:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('banner', '0056_merge_20191202_1838'),
    ]

    operations = [
        migrations.AddField(
            model_name='banner',
            name='body',
            field=models.CharField(blank=True, max_length=200000, null=True),
        ),
    ]