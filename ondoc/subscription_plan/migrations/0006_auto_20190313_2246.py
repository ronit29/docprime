# Generated by Django 2.0.5 on 2019-03-13 17:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subscription_plan', '0005_auto_20190313_1344'),
    ]

    operations = [
        migrations.AddField(
            model_name='plan',
            name='enabled',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='planfeature',
            name='enabled',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='planfeaturemapping',
            name='enabled',
            field=models.BooleanField(default=True),
        ),
    ]
