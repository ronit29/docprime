# Generated by Django 2.0.5 on 2018-06-14 07:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0038_labtest_test_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='labtest',
            name='name',
            field=models.CharField(max_length=200, unique=True),
        ),
        migrations.AlterField(
            model_name='labtest',
            name='why',
            field=models.TextField(blank=True),
        ),
    ]
