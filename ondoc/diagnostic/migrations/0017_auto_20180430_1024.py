# Generated by Django 2.0.2 on 2018-04-30 04:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0016_auto_20180428_1356'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lab',
            name='agreed_rate_list',
            field=models.FileField(blank=True, null=True, upload_to='lab/docs'),
        ),
    ]
