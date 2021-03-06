# Generated by Django 2.0.5 on 2018-09-18 10:56

import django.contrib.postgres.fields
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0112_auto_20180917_1653'),
    ]

    operations = [
        migrations.CreateModel(
            name='PracticeSpecialization',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=200, unique=True)),
                ('general_specialization_ids', django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(blank=True, null=True), size=100)),
            ],
            options={
                'db_table': 'practice_specialization',
            },
        ),
        migrations.CreateModel(
            name='SpecializationDepartmentMapping',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('department', models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to='doctor.SpecializationDepartment')),
                ('specialization', models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to='doctor.PracticeSpecialization')),
            ],
            options={
                'db_table': 'specialization_department_mapping',
            },
        ),
        migrations.AddField(
            model_name='practicespecialization',
            name='department',
            field=models.ManyToManyField(related_name='departments', through='doctor.SpecializationDepartmentMapping', to='doctor.SpecializationDepartment'),
        ),
        migrations.AddField(
            model_name='practicespecialization',
            name='specialization_field',
            field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to='doctor.SpecializationField'),
        ),
    ]
