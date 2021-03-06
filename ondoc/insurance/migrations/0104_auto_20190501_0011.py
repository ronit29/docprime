# Generated by Django 2.0.5 on 2019-04-30 18:41

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('insurance', '0103_merge_20190430_1737'),
    ]

    operations = [
        migrations.AlterField(
            model_name='insurancemis',
            name='attachment_file',
            field=models.FileField(default=None, null=True, upload_to='insurance/mis', validators=[django.core.validators.FileExtensionValidator(allowed_extensions=['zip', 'pdf', 'xls', 'xlsx'])]),
        ),
        migrations.AlterField(
            model_name='insurancemis',
            name='attachment_type',
            field=models.CharField(choices=[('ALL_MIS_ZIP', 'ALL_MIS_ZIP'), ('USER_INSURANCE_DOCTOR_RESOURCE', 'USER_INSURANCE_DOCTOR_RESOURCE'), ('USER_INSURANCE_LAB_RESOURCE', 'USER_INSURANCE_LAB_RESOURCE'), ('USER_INSURANCE_RESOURCE', 'USER_INSURANCE_RESOURCE')], max_length=100),
        ),
    ]
