# Generated by Django 2.0.5 on 2019-01-29 06:49

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0145_merge_20190108_1624'),
        ('contenttypes', '0002_remove_content_type_name'),
        ('integrations', '0007_auto_20190124_1406'),
    ]

    operations = [
        migrations.CreateModel(
            name='IntegratorProfileMapping',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('object_id', models.PositiveIntegerField()),
                ('integrator_class_name', models.CharField(max_length=40)),
                ('service_type', models.CharField(choices=[('LabTest', 'PROFILES')], default=None, max_length=30)),
                ('integrator_product_data', django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True)),
                ('integrator_package_name', models.CharField(default=None, max_length=60)),
                ('is_active', models.BooleanField(default=False)),
                ('content_type', models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to='contenttypes.ContentType')),
                ('package', models.ForeignKey(limit_choices_to={'is_package': True}, null=True, on_delete=django.db.models.deletion.CASCADE, to='diagnostic.LabTest')),
            ],
            options={
                'db_table': 'integrator_profile_mapping',
            },
        ),
        migrations.AlterField(
            model_name='integratormapping',
            name='test',
            field=models.ForeignKey(limit_choices_to={'is_package': False}, null=True, on_delete=django.db.models.deletion.CASCADE, to='diagnostic.LabTest'),
        ),
    ]
