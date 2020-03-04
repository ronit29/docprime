# Generated by Django 2.0.5 on 2020-02-26 12:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('plus', '0061_auto_20200225_1844'),
    ]

    operations = [
        migrations.AlterField(
            model_name='plusplanparameters',
            name='key',
            field=models.CharField(choices=[('DOCTOR_CONSULT_AMOUNT', 'DOCTOR_CONSULT_AMOUNT'), ('DOCTOR_CONSULT_COUNT', 'DOCTOR_CONSULT_COUNT'), ('DOCTOR_CONSULT_DISCOUNT', 'DOCTOR_CONSULT_DISCOUNT'), ('DOCTOR_CONVENIENCE_PERCENTAGE', 'DOCTOR_CONVENIENCE_PERCENTAGE'), ('DOCTOR_MAXIMUM_CAPPING_AMOUNT', 'DOCTOR_MAXIMUM_CAPPING_AMOUNT'), ('DOCTOR_MAX_DISCOUNTED_AMOUNT', 'DOCTOR_MAX_DISCOUNTED_AMOUNT'), ('DOCTOR_MINIMUM_CAPPING_AMOUNT', 'DOCTOR_MINIMUM_CAPPING_AMOUNT'), ('DOCTOR_MIN_DISCOUNTED_AMOUNT', 'DOCTOR_MIN_DISCOUNTED_AMOUNT'), ('HEALTH_CHECKUPS_AMOUNT', 'HEALTH_CHECKUPS_AMOUNT'), ('HEALTH_CHECKUPS_COUNT', 'HEALTH_CHECKUPS_COUNT'), ('LABTEST_AMOUNT', 'LABTEST_AMOUNT'), ('LABTEST_COUNT', 'LABTEST_COUNT'), ('LAB_CONVENIENCE_PERCENTAGE', 'LAB_CONVENIENCE_PERCENTAGE'), ('LAB_DISCOUNT', 'LAB_DISCOUNT'), ('LAB_MAXIMUM_CAPPING_AMOUNT', 'LAB_MAXIMUM_CAPPING_AMOUNT'), ('LAB_MAX_DISCOUNTED_AMOUNT', 'LAB_MAX_DISCOUNTED_AMOUNT'), ('LAB_MINIMUM_CAPPING_AMOUNT', 'LAB_MINIMUM_CAPPING_AMOUNT'), ('LAB_MIN_DISCOUNTED_AMOUNT', 'LAB_MIN_DISCOUNTED_AMOUNT'), ('MEMBERS_COVERED_IN_PACKAGE', 'MEMBERS_COVERED_IN_PACKAGE'), ('ONLINE_CHAT_AMOUNT', 'ONLINE_CHAT_AMOUNT'), ('ONLINE_CHAT_COUNT', 'ONLINE_CHAT_COUNT'), ('PACKAGES_COVERED', 'PACKAGES_COVERED'), ('PACKAGE_DISCOUNT', 'PACKAGE_DISCOUNT'), ('PACKAGE_IDS', 'PACKAGE_IDS'), ('PACKAGE_MAX_DISCOUNTED_AMOUNT', 'PACKAGE_MAX_DISCOUNTED_AMOUNT'), ('PACKAGE_MIN_DISCOUNTED_AMOUNT', 'PACKAGE_MIN_DISCOUNTED_AMOUNT'), ('PERCENTAGE_DISCOUNT', 'PERCENTAGE_DISCOUNT'), ('SPECIALIZATIONS', 'SPECIALIZATIONS'), ('TOTAL_TEST_COVERED_IN_PACKAGE', 'TOTAL_TEST_COVERED_IN_PACKAGE'), ('TOTAL_WORTH', 'TOTAL_WORTH')], max_length=100),
        ),
    ]
