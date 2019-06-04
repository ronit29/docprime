# Generated by Django 2.0.5 on 2019-04-01 08:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0234_merge_20190329_1825'),
    ]

    operations = [
        migrations.AddField(
            model_name='hospital',
            name='is_cod_enabled',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='hospital',
            name='is_prepaid_enabled',
            field=models.BooleanField(default=True),
        ),
    ]