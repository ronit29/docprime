# Generated by Django 2.0.5 on 2018-10-11 14:52

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seo', '0006_auto_20181011_1934'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sitemapmanger',
            name='file',
            field=models.FileField(upload_to='seo', validators=[django.core.validators.FileExtensionValidator(allowed_extensions=['xml'])]),
        ),
    ]
