# Generated by Django 2.0.5 on 2019-04-30 10:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('location', '0086_auto_20190430_1611'),
    ]

    operations = [
        migrations.AlterField(
            model_name='compareseourls',
            name='url',
            field=models.URLField(db_index=True, max_length=2000, null=True, unique=True),
        ),
    ]
