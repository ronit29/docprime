# Generated by Django 2.0.5 on 2019-11-11 06:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('plus', '0040_auto_20191108_1539'),
    ]

    operations = [
        migrations.AddField(
            model_name='plusplanutmsources',
            name='create_lead',
            field=models.NullBooleanField(),
        ),
        migrations.AlterField(
            model_name='plusplanutmsources',
            name='source',
            field=models.CharField(max_length=100, unique=True),
        ),
    ]