# Generated by Django 2.0.5 on 2019-06-24 06:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0209_labtest_insurance_cutoff_price'),
    ]

    operations = [
        migrations.AddField(
            model_name='labappointment',
            name='hospital_reference_id',
            field=models.CharField(blank=True, max_length=1000, null=True),
        ),
    ]