# Generated by Django 2.0.5 on 2020-01-08 07:41

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0239_auto_20191223_1832'),
    ]

    operations = [
        migrations.AddField(
            model_name='commonpackage',
            name='svg_icon',
            field=models.FileField(null=True, upload_to='diagnostic/common_package_icons', validators=[django.core.validators.FileExtensionValidator(allowed_extensions=['svg'])]),
        ),
        migrations.AddField(
            model_name='commontest',
            name='svg_icon',
            field=models.FileField(null=True, upload_to='diagnostic/common_test_icons', validators=[django.core.validators.FileExtensionValidator(allowed_extensions=['svg'])]),
        ),
    ]
