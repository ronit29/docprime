# Generated by Django 2.0.5 on 2020-02-25 06:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('plus', '0060_auto_20200224_1449'),
    ]

    operations = [
        migrations.AlterField(
            model_name='plusplans',
            name='priority',
            field=models.PositiveIntegerField(blank=True, default=0, null=True),
        ),
    ]