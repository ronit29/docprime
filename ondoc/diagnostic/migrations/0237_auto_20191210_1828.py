# Generated by Django 2.0.5 on 2019-12-10 12:58

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0236_merge_20191128_1735'),
    ]

    operations = [
        migrations.AlterField(
            model_name='commontest',
            name='icon',
            field=models.FileField(null=True, upload_to='diagnostic/common_test_icons', validators=[django.core.validators.FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'svg'])]),
        ),
        migrations.AlterField(
            model_name='labtestcategory',
            name='icon',
            field=models.FileField(blank=True, null=True, upload_to='test/image', validators=[django.core.validators.FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'svg'])]),
        ),
    ]
