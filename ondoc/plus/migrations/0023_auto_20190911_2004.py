# Generated by Django 2.0.5 on 2019-09-11 14:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('plus', '0022_plusappointmentmapping_amount'),
    ]

    operations = [
        migrations.AlterField(
            model_name='plusplanparameters',
            name='key',
            field=models.CharField(choices=[('DOCTOR_CONSULT_AMOUNT', 'DOCTOR_CONSULT_AMOUNT'), ('DOCTOR_CONSULT_COUNT', 'DOCTOR_CONSULT_COUNT'), ('HEALTH_CHECKUPS_AMOUNT', 'HEALTH_CHECKUPS_AMOUNT'), ('HEALTH_CHECKUPS_COUNT', 'HEALTH_CHECKUPS_COUNT'), ('MEMBERS_COVERED_IN_PACKAGE', 'MEMBERS_COVERED_IN_PACKAGE'), ('ONLINE_CHAT_AMOUNT', 'ONLINE_CHAT_AMOUNT'), ('ONLINE_CHAT_COUNT', 'ONLINE_CHAT_COUNT'), ('PACKAGES_COVERED', 'PACKAGES_COVERED'), ('PACKAGE_IDS', 'PACKAGE_IDS'), ('PERCENTAGE_DISCOUNT', 'PERCENTAGE_DISCOUNT'), ('SPECIALIZATIONS', 'SPECIALIZATIONS'), ('TOTAL_TEST_COVERED_IN_PACKAGE', 'TOTAL_TEST_COVERED_IN_PACKAGE')], max_length=100),
        ),
    ]
