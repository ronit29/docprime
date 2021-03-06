# Generated by Django 2.0.5 on 2018-09-13 11:05

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0086_merge_20180904_1747'),
    ]

    operations = [
        migrations.AddField(
            model_name='lab',
            name='ppc_rate_list',
            field=models.FileField(blank=True, max_length=200, null=True, upload_to='lab/docs', validators=[django.core.validators.FileExtensionValidator(allowed_extensions=['pdf', 'xls', 'xlsx'])]),
        ),
        migrations.AlterField(
            model_name='lab',
            name='agreed_rate_list',
            field=models.FileField(blank=True, max_length=200, null=True, upload_to='lab/docs', validators=[django.core.validators.FileExtensionValidator(allowed_extensions=['pdf', 'xls', 'xlsx'])]),
        ),
    ]
