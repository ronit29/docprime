# Generated by Django 2.0.5 on 2019-06-21 12:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0209_labtest_insurance_cutoff_price'),
    ]

    operations = [
        migrations.AddField(
            model_name='labappointment',
            name='reports_physically_collected',
            field=models.NullBooleanField(),
        ),
    ]
