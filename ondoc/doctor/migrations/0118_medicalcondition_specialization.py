# Generated by Django 2.0.5 on 2018-09-20 09:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0117_auto_20180920_1520'),
    ]

    operations = [
        migrations.AddField(
            model_name='medicalcondition',
            name='specialization',
            field=models.ManyToManyField(through='doctor.MedicalConditionSpecialization', to='doctor.PracticeSpecialization'),
        ),
    ]