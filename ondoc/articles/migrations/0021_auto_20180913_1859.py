# Generated by Django 2.0.5 on 2018-09-13 13:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('articles', '0020_auto_20180912_1840'),
    ]

    operations = [
        migrations.AlterField(
            model_name='article',
            name='body',
            field=models.CharField(max_length=200000),
        ),
    ]
