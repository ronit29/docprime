# Generated by Django 2.0.5 on 2019-01-07 13:56

from django.db import migrations, models
import ondoc.insurance.models


class Migration(migrations.Migration):

    dependencies = [
        ('insurance', '0061_auto_20190103_1808'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userinsurance',
            name='receipt_number',
            field=models.BigIntegerField(default=ondoc.insurance.models.generate_insurance_reciept_number, unique=True),
        ),
    ]
