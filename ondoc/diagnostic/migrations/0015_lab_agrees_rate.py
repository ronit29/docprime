# Generated by Django 2.0.2 on 2018-04-28 08:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0014_auto_20180427_1159'),
    ]

    operations = [
        migrations.AddField(
            model_name='lab',
            name='agrees_rate',
            field=models.FileField(null=True, upload_to='lab/docs'),
        ),
    ]
