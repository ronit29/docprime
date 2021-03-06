# Generated by Django 2.0.2 on 2018-04-11 10:43

from django.conf import settings
import django.contrib.gis.db.models.fields
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Doctor',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('data_status', models.PositiveSmallIntegerField(choices=[(1, 'In Progress'), (2, 'Submitted For QC Check'), (3, 'QC approved')], default=1, editable=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=200)),
                ('gender', models.CharField(blank=True, choices=[('', 'Select'), ('m', 'Male'), ('f', 'Female'), ('o', 'Other')], default=None, max_length=2)),
                ('practice_duration', models.PositiveSmallIntegerField(blank=True, default=None, null=True, validators=[django.core.validators.MaxValueValidator(100), django.core.validators.MinValueValidator(1)])),
                ('about', models.CharField(blank=True, max_length=2000)),
                ('registration_details', models.CharField(blank=True, max_length=200)),
                ('additional_details', models.CharField(blank=True, max_length=2000)),
                ('country_code', models.PositiveSmallIntegerField(blank=True, default=91, null=True)),
                ('phone_number', models.BigIntegerField(blank=True, null=True, validators=[django.core.validators.MaxValueValidator(9999999999), django.core.validators.MinValueValidator(1000000000)])),
                ('is_phone_number_verified', models.BooleanField(default=False, verbose_name='Phone Number Verified')),
                ('email', models.EmailField(blank=True, max_length=100)),
                ('is_email_verified', models.BooleanField(default=False, verbose_name='Email Verified')),
                ('created_by', models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'doctor',
            },
        ),
        migrations.CreateModel(
            name='DoctorAssociation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=200)),
                ('doctor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.Doctor')),
            ],
            options={
                'db_table': 'doctor_association',
            },
        ),
        migrations.CreateModel(
            name='DoctorAward',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=200)),
                ('doctor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.Doctor')),
            ],
            options={
                'db_table': 'doctor_awards',
            },
        ),
        migrations.CreateModel(
            name='DoctorDocument',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('width', models.PositiveSmallIntegerField(editable=False)),
                ('height', models.PositiveSmallIntegerField(editable=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.ImageField(height_field='height', upload_to='doctor/documents', width_field='width')),
                ('doctor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.Doctor')),
            ],
            options={
                'db_table': 'doctor_document',
            },
        ),
        migrations.CreateModel(
            name='DoctorExperience',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('hospital', models.CharField(max_length=200)),
                ('start_year', models.PositiveSmallIntegerField(blank=True, default=None, null=True, validators=[django.core.validators.MinValueValidator(1950)])),
                ('end_year', models.PositiveSmallIntegerField(blank=True, default=None, null=True, validators=[django.core.validators.MinValueValidator(1950)])),
                ('doctor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.Doctor')),
            ],
            options={
                'db_table': 'doctor_experience',
            },
        ),
        migrations.CreateModel(
            name='DoctorHospital',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('day', models.PositiveSmallIntegerField(choices=[(1, 'Monday'), (2, 'Tuesday'), (3, 'Wednesday'), (4, 'Thursday'), (5, 'Friday'), (6, 'Saturday'), (7, 'Sunday')])),
                ('start', models.PositiveSmallIntegerField(choices=[(6, '6 AM'), (7, '7 AM'), (8, '8 AM'), (9, '9 AM'), (10, '10 AM'), (11, '11 AM'), (12, '12 PM'), (13, '1 PM'), (14, '2 PM'), (15, '3 PM'), (16, '4 PM'), (17, '5 PM'), (18, '6 PM'), (19, '7 PM'), (20, '8 PM'), (21, '9 PM'), (22, '10 PM'), (23, '11 PM')])),
                ('end', models.PositiveSmallIntegerField(choices=[(6, '6 AM'), (7, '7 AM'), (8, '8 AM'), (9, '9 AM'), (10, '10 AM'), (11, '11 AM'), (12, '12 PM'), (13, '1 PM'), (14, '2 PM'), (15, '3 PM'), (16, '4 PM'), (17, '5 PM'), (18, '6 PM'), (19, '7 PM'), (20, '8 PM'), (21, '9 PM'), (22, '10 PM'), (23, '11 PM')])),
                ('fees', models.PositiveSmallIntegerField()),
                ('mrp', models.PositiveSmallIntegerField(null=True)),                
                ('doctor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.Doctor')),
            ],
            options={
                'db_table': 'doctor_hospital',
            },
        ),
        migrations.CreateModel(
            name='DoctorImage',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('width', models.PositiveSmallIntegerField(editable=False)),
                ('height', models.PositiveSmallIntegerField(editable=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.ImageField(height_field='height', upload_to='doctor/images', width_field='width')),
                ('doctor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.Doctor')),
            ],
            options={
                'db_table': 'doctor_image',
            },
        ),
        migrations.CreateModel(
            name='DoctorLanguage',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('doctor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.Doctor')),
            ],
            options={
                'db_table': 'doctor_language',
            },
        ),
        migrations.CreateModel(
            name='DoctorMedicalService',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('doctor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.Doctor')),
            ],
            options={
                'db_table': 'doctor_medical_service',
            },
        ),
        migrations.CreateModel(
            name='DoctorQualification',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('doctor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.Doctor')),
            ],
            options={
                'db_table': 'doctor_qualification',
            },
        ),
        migrations.CreateModel(
            name='Hospital',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('data_status', models.PositiveSmallIntegerField(choices=[(1, 'In Progress'), (2, 'Submitted For QC Check'), (3, 'QC approved')], default=1, editable=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(blank=True, max_length=200)),
                ('address', models.CharField(max_length=500)),
                ('location', django.contrib.gis.db.models.fields.PointField(blank=True, geography=True, null=True, srid=4326)),
                ('location_error', models.PositiveIntegerField(blank=True, null=True)),
                ('years_operational', models.PositiveSmallIntegerField(blank=True, null=True, validators=[django.core.validators.MaxValueValidator(1), django.core.validators.MinValueValidator(200)])),
                ('registration_number', models.CharField(blank=True, max_length=500)),
                ('building', models.CharField(blank=True, max_length=100)),
                ('sublocality', models.CharField(blank=True, max_length=100)),
                ('locality', models.CharField(blank=True, max_length=100)),
                ('city', models.CharField(blank=True, max_length=100)),
                ('state', models.CharField(blank=True, max_length=100)),
                ('pin_code', models.PositiveIntegerField(blank=True, null=True)),
                ('hospital_type', models.PositiveSmallIntegerField(blank=True, choices=[('', 'Select'), (1, 'Private'), (2, 'Clinic'), (3, 'Hospital')], null=True)),
                ('created_by', models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'hospital',
            },
        ),
        migrations.CreateModel(
            name='HospitalDocument',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('width', models.PositiveSmallIntegerField(editable=False)),
                ('height', models.PositiveSmallIntegerField(editable=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.ImageField(height_field='height', upload_to='hospital/documents', width_field='width')),
                ('hospital', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.Hospital')),
            ],
            options={
                'db_table': 'hospital_document',
            },
        ),
        migrations.CreateModel(
            name='HospitalImage',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('width', models.PositiveSmallIntegerField(editable=False)),
                ('height', models.PositiveSmallIntegerField(editable=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.ImageField(height_field='height', upload_to='hospital/images', width_field='width')),
                ('hospital', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.Hospital')),
            ],
            options={
                'db_table': 'hospital_image',
            },
        ),
        migrations.CreateModel(
            name='Language',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=100)),
                ('short_name', models.CharField(blank=True, max_length=20)),
            ],
            options={
                'db_table': 'language',
            },
        ),
        migrations.CreateModel(
            name='MedicalService',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=500)),
                ('description', models.CharField(blank=True, max_length=500)),
            ],
            options={
                'db_table': 'medical_services',
            },
        ),
        migrations.CreateModel(
            name='Qualification',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=200)),
                ('created_by', models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'qualification',
            },
        ),
        migrations.CreateModel(
            name='Specialization',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=200)),
                ('human_readable_name', models.CharField(blank=True, max_length=200)),
                ('created_by', models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'specialization',
            },
        ),
        migrations.AddField(
            model_name='doctorqualification',
            name='qualification',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.Qualification'),
        ),
        migrations.AddField(
            model_name='doctorqualification',
            name='specialization',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='doctor.Specialization'),
        ),
        migrations.AddField(
            model_name='doctormedicalservice',
            name='service',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.MedicalService'),
        ),
        migrations.AddField(
            model_name='doctorlanguage',
            name='language',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.Language'),
        ),
        migrations.AddField(
            model_name='doctorhospital',
            name='hospital',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.Hospital'),
        ),
        migrations.AddField(
            model_name='doctor',
            name='hospitals',
            field=models.ManyToManyField(through='doctor.DoctorHospital', to='doctor.Hospital'),
        ),
        migrations.AlterUniqueTogether(
            name='doctorqualification',
            unique_together={('doctor', 'qualification', 'specialization')},
        ),
        migrations.AlterUniqueTogether(
            name='doctormedicalservice',
            unique_together={('doctor', 'service')},
        ),
        migrations.AlterUniqueTogether(
            name='doctorlanguage',
            unique_together={('doctor', 'language')},
        ),
    ]
