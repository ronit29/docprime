# Generated by Django 2.0.5 on 2018-08-21 07:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('articles', '0011_auto_20180821_1208'),
    ]

    operations = [
        migrations.AddField(
            model_name='article',
            name='description',
            field=models.CharField(max_length=500, null=True),
        ),
        migrations.AddField(
            model_name='article',
            name='keywords',
            field=models.CharField(max_length=256, null=True),
        ),
        migrations.AddField(
            model_name='articlecategory',
            name='identifier',
            field=models.CharField(max_length=48, null=True),
        ),
        migrations.AddField(
            model_name='articlecategory',
            name='url',
            field=models.CharField(max_length=500, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name='article',
            name='title',
            field=models.CharField(max_length=500, unique=True),
        ),
        migrations.AlterField(
            model_name='article',
            name='url',
            field=models.CharField(max_length=500, null=True, unique=True),
        ),
    ]