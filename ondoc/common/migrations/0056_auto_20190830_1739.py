# Generated by Django 2.0.5 on 2019-08-30 12:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0055_merge_20190711_1547'),
    ]

    operations = [
        migrations.AlterField(
            model_name='blockedstates',
            name='state_name',
            field=models.CharField(choices=[('INSURANCE', 'INSURANCE'), ('LOGIN', 'LOGIN'), ('VIP', 'VIP')], max_length=50, unique=True),
        ),
    ]