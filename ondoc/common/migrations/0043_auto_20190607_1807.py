# Generated by Django 2.0.5 on 2019-06-07 12:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0042_auto_20190607_1802'),
    ]

    operations = [
        migrations.AlterField(
            model_name='blockedstates',
            name='state_name',
            field=models.CharField(choices=[('INSURANCE', 'INSURANCE'), ('LOGIN', 'LOGIN')], max_length=50, unique=True),
        ),
    ]
