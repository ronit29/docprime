# Generated by Django 2.0.5 on 2018-09-14 11:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0088_lab_enabled'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lab',
            name='enabled',
            field=models.BooleanField(default=True, verbose_name='Is Enabled'),
        ),
    ]
