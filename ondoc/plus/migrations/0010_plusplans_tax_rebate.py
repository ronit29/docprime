# Generated by Django 2.0.5 on 2019-08-29 10:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('plus', '0009_auto_20190829_1356'),
    ]

    operations = [
        migrations.AddField(
            model_name='plusplans',
            name='tax_rebate',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
