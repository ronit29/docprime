# Generated by Django 2.0.5 on 2018-06-15 12:35

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Order',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('product_id', models.SmallIntegerField(choices=[(1, 'Doctor Appointment'), (2, 'Lab Appointment')])),
                ('appointment_id', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('action', models.PositiveSmallIntegerField(blank=True, choices=[('', 'Select'), (1, 'Reschedule'), (2, 'Create')], null=True)),
                ('action_data', django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True)),
                ('amount', models.SmallIntegerField(blank=True, null=True)),
                ('payment_status', models.PositiveSmallIntegerField(choices=[(1, 'Payment Accepted'), (0, 'Payment Pending')], default=0)),
                ('error_status', models.CharField(max_length=250, verbose_name='Error')),
                ('is_viewable', models.BooleanField(default=False, verbose_name='Is Viewable')),
            ],
            options={
                'db_table': 'order',
            },
        ),
    ]