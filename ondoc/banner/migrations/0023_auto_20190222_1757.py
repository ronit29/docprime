# Generated by Django 2.0.5 on 2019-02-22 12:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('banner', '0022_banner_radius'),
    ]

    operations = [
        migrations.AlterField(
            model_name='banner',
            name='radius',
            field=models.FloatField(blank=True, default=0, null=True),
        ),
    ]