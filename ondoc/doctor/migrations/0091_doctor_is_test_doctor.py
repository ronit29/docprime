# Generated by Django 2.0.5 on 2018-08-03 07:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0090_auto_20180802_1151'),
    ]

    operations = [
        migrations.AddField(
            model_name='doctor',
            name='is_test_doctor',
            field=models.BooleanField(default=False, verbose_name='Is Test Doctor'),
        ),
    ]
