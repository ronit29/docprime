# Generated by Django 2.0.2 on 2018-04-16 03:39

import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0007_doctoraward_year'),
    ]

    operations = [
        migrations.CreateModel(
            name='HospitalAccreditation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=200)),
            ],
            options={
                'db_table': 'hospital_accreditation',
            },
        ),
        migrations.CreateModel(
            name='HospitalAward',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=200)),
                ('year', models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1900)])),
            ],
            options={
                'db_table': 'hospital_award',
            },
        ),
        migrations.CreateModel(
            name='HospitalCertification',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=200)),
            ],
            options={
                'db_table': 'hospital_certification',
            },
        ),
        migrations.CreateModel(
            name='HospitalNetwork',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=100)),
                ('operational_since', models.PositiveSmallIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(1900)])),
                ('about', models.CharField(blank=True, max_length=2000)),
                ('network_size', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('building', models.CharField(blank=True, max_length=100)),
                ('sublocality', models.CharField(blank=True, max_length=100)),
                ('locality', models.CharField(blank=True, max_length=100)),
                ('city', models.CharField(blank=True, max_length=100)),
                ('state', models.CharField(blank=True, max_length=100)),
                ('country', models.CharField(blank=True, max_length=100)),
                ('pin_code', models.PositiveIntegerField(blank=True, null=True)),
            ],
            options={
                'db_table': 'hospital_network',
            },
        ),
        migrations.CreateModel(
            name='HospitalNetworkAccreditation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=200)),
                ('network', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.HospitalNetwork')),
            ],
            options={
                'db_table': 'hospital_network_accreditation',
            },
        ),
        migrations.CreateModel(
            name='HospitalNetworkAward',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=200)),
                ('year', models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1900)])),
                ('network', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.HospitalNetwork')),
            ],
            options={
                'db_table': 'hospital_network_award',
            },
        ),
        migrations.CreateModel(
            name='HospitalNetworkCertification',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=200)),
                ('network', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.HospitalNetwork')),
            ],
            options={
                'db_table': 'hospital_network_certification',
            },
        ),
        migrations.CreateModel(
            name='HospitalSpeciality',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=200)),
            ],
            options={
                'db_table': 'hospital_speciality',
            },
        ),
        migrations.AddField(
            model_name='hospital',
            name='country',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AlterField(
            model_name='doctoraward',
            name='year',
            field=models.PositiveSmallIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(1900)]),
        ),
        migrations.AlterModelTable(
            name='medicalservice',
            table='medical_service',
        ),
        migrations.AddField(
            model_name='hospitalspeciality',
            name='hospital',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.Hospital'),
        ),
        migrations.AddField(
            model_name='hospitalcertification',
            name='hospital',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.Hospital'),
        ),
        migrations.AddField(
            model_name='hospitalaward',
            name='hospital',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.Hospital'),
        ),
        migrations.AddField(
            model_name='hospitalaccreditation',
            name='hospital',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.Hospital'),
        ),
    ]
