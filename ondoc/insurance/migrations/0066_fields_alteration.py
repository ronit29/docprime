# Generated by Django 2.0.5 on 2019-02-04 09:39

from django.db import migrations, models
import ondoc.insurance.models

class Migration(migrations.Migration):

    dependencies = [
        ('insurance', '0065_sequence_creation'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userinsurance',
            name='policy_number',
            field=models.CharField(default=ondoc.insurance.models.generate_insurance_policy_number, max_length=100, blank=False, null=False, unique=True),
        ),
        migrations.AlterField(
            model_name='userinsurance',
            name='receipt_number',
            field=models.BigIntegerField(default=ondoc.insurance.models.generate_insurance_reciept_number, null=False, unique=True),
        ),

    ]
