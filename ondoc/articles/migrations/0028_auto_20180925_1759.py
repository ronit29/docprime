# Generated by Django 2.0.5 on 2018-09-25 12:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('articles', '0027_auto_20180925_1757'),
    ]

    operations = [
        migrations.AlterField(
            model_name='articlecategory',
            name='description',
            field=models.CharField(blank=True, max_length=200000, null=True),
        ),
        migrations.AlterField(
            model_name='articlecategory',
            name='title',
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
    ]
