# Generated by Django 2.0.5 on 2019-05-03 12:18

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seo', '0014_auto_20190118_1340'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sitemapmanger',
            name='file',
            field=models.FileField(upload_to='seo', validators=[django.core.validators.FileExtensionValidator(allowed_extensions=['xml, gzip'])]),
        ),
    ]
