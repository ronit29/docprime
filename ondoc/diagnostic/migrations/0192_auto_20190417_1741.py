# Generated by Django 2.0.5 on 2019-04-17 12:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0191_auto_20190416_1745'),
    ]

    operations = [
        migrations.AddField(
            model_name='lab',
            name='auto_ivr_enabled',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='labnetwork',
            name='auto_ivr_enabled',
            field=models.BooleanField(default=True),
        ),
    ]
