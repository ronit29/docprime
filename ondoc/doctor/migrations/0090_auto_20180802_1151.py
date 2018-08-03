# Generated by Django 2.0.2 on 2018-08-02 06:21

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0089_merge_20180802_1133'),
    ]

    operations = [
        migrations.AlterField(
            model_name='commonmedicalcondition',
            name='condition',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='common_condition', to='doctor.MedicalCondition'),
        ),
        migrations.AlterField(
            model_name='commonspecialization',
            name='specialization',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='common_specialization', to='doctor.Specialization'),
        ),
        migrations.AlterField(
            model_name='doctorassociation',
            name='doctor',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='associations', to='doctor.Doctor'),
        ),
        migrations.AlterField(
            model_name='doctoraward',
            name='doctor',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='awards', to='doctor.Doctor'),
        ),
        migrations.AlterField(
            model_name='doctordocument',
            name='doctor',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='documents', to='doctor.Doctor'),
        ),
        migrations.AlterField(
            model_name='doctoremail',
            name='doctor',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='emails', to='doctor.Doctor'),
        ),
        migrations.AlterField(
            model_name='doctorexperience',
            name='doctor',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='experiences', to='doctor.Doctor'),
        ),
        migrations.AlterField(
            model_name='doctorhospital',
            name='doctor',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='availability', to='doctor.Doctor'),
        ),
        migrations.AlterField(
            model_name='doctorhospital',
            name='hospital',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.Hospital'),
        ),
        migrations.AlterField(
            model_name='doctorimage',
            name='doctor',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='images', to='doctor.Doctor'),
        ),
        migrations.AlterField(
            model_name='doctorlanguage',
            name='doctor',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='languages', to='doctor.Doctor'),
        ),
        migrations.AlterField(
            model_name='doctorlanguage',
            name='language',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.Language'),
        ),
        migrations.AlterField(
            model_name='doctorleave',
            name='doctor',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='leaves', to='doctor.Doctor'),
        ),
        migrations.AlterField(
            model_name='doctormapping',
            name='doctor',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='doctor_mapping', to='doctor.Doctor'),
        ),
        migrations.AlterField(
            model_name='doctormapping',
            name='profile_to_be_shown',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='profile_to_be_shown_mapping', to='doctor.Doctor'),
        ),
        migrations.AlterField(
            model_name='doctormedicalservice',
            name='doctor',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='medical_services', to='doctor.Doctor'),
        ),
        migrations.AlterField(
            model_name='doctormedicalservice',
            name='service',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.MedicalService'),
        ),
        migrations.AlterField(
            model_name='doctormobile',
            name='doctor',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mobiles', to='doctor.Doctor'),
        ),
        migrations.AlterField(
            model_name='doctorqualification',
            name='college',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='doctor.College'),
        ),
        migrations.AlterField(
            model_name='doctorqualification',
            name='doctor',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='qualifications', to='doctor.Doctor'),
        ),
        migrations.AlterField(
            model_name='doctorqualification',
            name='qualification',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.Qualification'),
        ),
        migrations.AlterField(
            model_name='doctorqualification',
            name='specialization',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='doctor.Specialization'),
        ),
        migrations.AlterField(
            model_name='doctorspecialization',
            name='doctor',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='doctorspecializations', to='doctor.Doctor'),
        ),
        migrations.AlterField(
            model_name='doctorspecialization',
            name='specialization',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.GeneralSpecialization'),
        ),
        migrations.AlterField(
            model_name='hospitalaccreditation',
            name='hospital',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.Hospital'),
        ),
        migrations.AlterField(
            model_name='hospitalaward',
            name='hospital',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.Hospital'),
        ),
        migrations.AlterField(
            model_name='hospitalcertification',
            name='hospital',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.Hospital'),
        ),
        migrations.AlterField(
            model_name='hospitaldocument',
            name='hospital',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='hospital_documents', to='doctor.Hospital'),
        ),
        migrations.AlterField(
            model_name='hospitalimage',
            name='hospital',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.Hospital'),
        ),
        migrations.AlterField(
            model_name='hospitalnetworkaccreditation',
            name='network',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.HospitalNetwork'),
        ),
        migrations.AlterField(
            model_name='hospitalnetworkaward',
            name='network',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.HospitalNetwork'),
        ),
        migrations.AlterField(
            model_name='hospitalnetworkcertification',
            name='network',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.HospitalNetwork'),
        ),
        migrations.AlterField(
            model_name='hospitalnetworkemail',
            name='network',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.HospitalNetwork'),
        ),
        migrations.AlterField(
            model_name='hospitalnetworkhelpline',
            name='network',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.HospitalNetwork'),
        ),
        migrations.AlterField(
            model_name='hospitalnetworkmanager',
            name='network',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.HospitalNetwork'),
        ),
        migrations.AlterField(
            model_name='hospitalspeciality',
            name='hospital',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.Hospital'),
        ),
        migrations.AlterField(
            model_name='medicalconditionspecialization',
            name='medical_condition',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.MedicalCondition'),
        ),
        migrations.AlterField(
            model_name='medicalconditionspecialization',
            name='specialization',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.Specialization'),
        ),
        migrations.AlterField(
            model_name='prescription',
            name='appointment',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.OpdAppointment'),
        ),
        migrations.AlterField(
            model_name='prescriptionfile',
            name='prescription',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.Prescription'),
        ),
    ]