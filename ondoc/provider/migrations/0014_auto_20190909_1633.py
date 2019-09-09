# Generated by Django 2.0.5 on 2019-09-09 11:03

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0226_lab_is_b2b'),
        ('doctor', '0313_hospital_is_partner_lab_enabled'),
        ('provider', '0013_auto_20190905_1530'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProviderLabSamplesCollectOrder',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('patient_details', django.contrib.postgres.fields.jsonb.JSONField()),
                ('collection_datetime', models.DateTimeField(blank=True, null=True)),
                ('samples', django.contrib.postgres.fields.jsonb.JSONField(null=True)),
                ('available_lab_tests', models.ManyToManyField(related_name='tests_lab_samples_collect_order', to='diagnostic.AvailableLabTest')),
                ('doctor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='doc_lab_samples_collect_order', to='doctor.Doctor')),
                ('hospital', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='hosp_lab_samples_collect_order', to='doctor.Hospital')),
                ('lab', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lab_samples_collect_order', to='diagnostic.Lab')),
            ],
            options={
                'db_table': 'provider_lab_samples_collect_order',
            },
        ),
        migrations.CreateModel(
            name='ProviderLabTestSampleDetails',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('volume', models.PositiveIntegerField(blank=True, null=True)),
                ('fasting_required', models.BooleanField(default=False)),
                ('report_tat', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('reference_value', models.PositiveIntegerField(blank=True, null=True)),
                ('material_required', django.contrib.postgres.fields.jsonb.JSONField()),
                ('lab_test', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='sample_details', to='diagnostic.LabTest')),
                ('sample', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='details', to='provider.ProviderLabTestSamples')),
            ],
            options={
                'db_table': 'provider_lab_test_sample_details',
            },
        ),
        migrations.CreateModel(
            name='TestSamplesLabAlerts',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=128)),
            ],
            options={
                'db_table': 'test_samples_lab_alerts',
            },
        ),
        migrations.AddField(
            model_name='providerlabsamplescollectorder',
            name='lab_alerts',
            field=models.ManyToManyField(to='provider.TestSamplesLabAlerts'),
        ),
        migrations.AddField(
            model_name='providerlabsamplescollectorder',
            name='offline_patient',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='patient_lab_samples_collect_order', to='doctor.OfflinePatients'),
        ),
    ]
