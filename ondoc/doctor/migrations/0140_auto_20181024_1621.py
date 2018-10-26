# Generated by Django 2.0.5 on 2018-10-24 10:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0139_auto_20181024_1316'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='googledetailing',
            name='doc_place_sheet',
        ),
        migrations.AddField(
            model_name='googledetailing',
            name='address',
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name='googledetailing',
            name='clinic_address',
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name='googledetailing',
            name='clinic_hospital_name',
            field=models.CharField(max_length=128, null=True),
        ),
        migrations.AddField(
            model_name='googledetailing',
            name='doctor_clinic_address',
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name='googledetailing',
            name='identifier',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='googledetailing',
            name='name',
            field=models.CharField(max_length=64, null=True),
        ),
        migrations.DeleteModel(
            name='DoctorPlaceSheet',
        ),
    ]
