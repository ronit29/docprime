# Generated by Django 2.0.5 on 2019-04-29 09:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0248_auto_20190429_1232'),
    ]

    operations = [
        migrations.AlterField(
            model_name='searchscore',
            name='popularity_score',
            field=models.FloatField(default=None, null=True),
        ),
    ]
