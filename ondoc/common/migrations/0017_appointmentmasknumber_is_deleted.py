# Generated by Django 2.0.5 on 2019-02-07 07:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0016_auto_20190206_1913'),
    ]

    operations = [
        migrations.AddField(
            model_name='appointmentmasknumber',
            name='is_deleted',
            field=models.BooleanField(default=False),
        ),
    ]
