# Generated by Django 2.0.5 on 2019-02-06 13:33

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('integrations', '0008_auto_20190129_1219'),
    ]

    operations = [
        migrations.CreateModel(
            name='IntegratorResponse',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('object_id', models.PositiveIntegerField()),
                ('integrator_class_name', models.CharField(max_length=40)),
                ('lead_id', models.CharField(blank=True, max_length=40, null=True)),
                ('dp_order_id', models.CharField(blank=True, max_length=40, null=True)),
                ('integrator_order_id', models.CharField(blank=True, max_length=40, null=True)),
                ('response_data', django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True)),
                ('content_type', models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to='contenttypes.ContentType')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]