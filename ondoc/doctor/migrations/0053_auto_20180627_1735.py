# Generated by Django 2.0.5 on 2018-06-27 12:05

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0052_auto_20180627_1204'),
    ]

    operations = [
        migrations.CreateModel(
            name='MedicalConditionSpecialization',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('medical_condition', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.MedicalCondition')),
                ('specialization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.Specialization')),
            ],
            options={
                'db_table': 'medical_condition_specialization',
            },
        ),
        migrations.AddField(
            model_name='hospital',
            name='is_billing_enabled',
            field=models.BooleanField(default=False, verbose_name='Enabled for Billing'),
        ),
        migrations.AddField(
            model_name='hospitalnetwork',
            name='is_billing_enabled',
            field=models.BooleanField(default=False, verbose_name='Enabled for Billing'),
        ),
        migrations.AddField(
            model_name='medicalcondition',
            name='specialization',
            field=models.ManyToManyField(through='doctor.MedicalConditionSpecialization', to='doctor.Specialization'),
        ),
    ]
