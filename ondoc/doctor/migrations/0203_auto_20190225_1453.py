# Generated by Django 2.0.5 on 2019-02-25 09:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0202_providersignuplead'),
    ]

    operations = [
        migrations.AlterField(
            model_name='providersignuplead',
            name='phone_number',
            field=models.BigIntegerField(unique=True),
        ),
    ]
