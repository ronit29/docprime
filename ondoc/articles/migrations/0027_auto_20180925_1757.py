# Generated by Django 2.0.5 on 2018-09-25 12:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('articles', '0026_auto_20180925_1555'),
    ]

    operations = [
        migrations.AddField(
            model_name='articlecategory',
            name='description',
            field=models.CharField(max_length=200000, null=True),
        ),
        migrations.AddField(
            model_name='articlecategory',
            name='title',
            field=models.CharField(max_length=500, null=True),
        ),
    ]
