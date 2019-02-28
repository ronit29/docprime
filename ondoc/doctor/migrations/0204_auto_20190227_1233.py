# Generated by Django 2.0.5 on 2019-02-27 07:03

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0203_auto_20190227_1053'),
    ]

    operations = [
        migrations.CreateModel(
            name='HealthInsuranceProvider',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=100)),
            ],
            options={
                'db_table': 'health_insurance_provider',
            },
        ),
        migrations.CreateModel(
            name='HealthInsuranceProviderHospitalMapping',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('hospital', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='provider_mappings', to='doctor.Hospital')),
                ('provider', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='hospital_provider_mappings', to='doctor.HealthInsuranceProvider')),
            ],
            options={
                'db_table': 'hospital__health_insurance_provider_mapping',
            },
        ),
        migrations.AddField(
            model_name='hospital',
            name='health_insurance_providers',
            field=models.ManyToManyField(related_name='available_in_hospital', through='doctor.HealthInsuranceProviderHospitalMapping', to='doctor.HealthInsuranceProvider'),
        ),
        migrations.AlterUniqueTogether(
            name='healthinsuranceproviderhospitalmapping',
            unique_together={('hospital', 'provider')},
        ),
    ]
