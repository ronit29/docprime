# Generated by Django 2.0.5 on 2019-01-17 06:59

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0051_moneypool'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='moneypool',
            name='user',
        ),
    ]