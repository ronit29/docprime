# Generated by Django 2.0.5 on 2018-07-25 11:43

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0083_auto_20180725_1659'),
    ]

    operations = [
        migrations.AlterField(
            model_name='doctorclinictiming',
            name='doctor_clinic',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='availability', to='doctor.DoctorClinic'),
        ),
    ]
