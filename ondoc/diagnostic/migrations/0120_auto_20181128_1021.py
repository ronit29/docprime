# Generated by Django 2.0.5 on 2018-11-28 04:51

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0119_auto_20181116_1202'),
    ]

    operations = [
        migrations.AlterField(
            model_name='labreportfile',
            name='name',
            field=models.FileField(upload_to='lab_reports/', validators=[django.core.validators.FileExtensionValidator(allowed_extensions=['pdf', 'jfif', 'jpg', 'jpeg', 'png'])]),
        ),
    ]
