# Generated by Django 2.0.5 on 2018-11-21 07:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0120_merge_20181120_1236'),
    ]

    operations = [
        migrations.AddField(
            model_name='labtest',
            name='is_corporate',
            field=models.BooleanField(default=False),
        ),
    ]
