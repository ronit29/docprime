# Generated by Django 2.0.5 on 2018-06-27 12:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0049_merge_20180625_2045'),
    ]

    operations = [
        migrations.AddField(
            model_name='lab',
            name='is_billing_enabled',
            field=models.BooleanField(default=False, verbose_name='Enabled for Billing'),
        ),
        migrations.AddField(
            model_name='labnetwork',
            name='is_billing_enabled',
            field=models.BooleanField(default=False, verbose_name='Enabled for Billing'),
        ),
    ]
