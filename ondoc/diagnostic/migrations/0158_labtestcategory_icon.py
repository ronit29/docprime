# Generated by Django 2.0.5 on 2019-02-19 13:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0157_auto_20190214_1547'),
    ]

    operations = [
        migrations.AddField(
            model_name='labtestcategory',
            name='icon',
            field=models.ImageField(null=True, upload_to='test/image'),
        ),
    ]
