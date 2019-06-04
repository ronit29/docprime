# Generated by Django 2.0.5 on 2019-02-19 07:03

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('procedure', '0019_commonprocedure'),
    ]

    operations = [
        migrations.AlterField(
            model_name='doctorclinicprocedure',
            name='doctor_clinic',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='procedures_from_doctor_clinic', to='doctor.DoctorClinic'),
        ),
        migrations.AlterField(
            model_name='doctorclinicprocedure',
            name='procedure',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='doctor_clinics_from_procedure', to='procedure.Procedure'),
        ),
    ]