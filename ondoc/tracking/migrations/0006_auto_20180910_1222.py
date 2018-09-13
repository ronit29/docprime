# Generated by Django 2.0.5 on 2018-09-10 06:52

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('tracking', '0005_visits_ip_address'),
    ]

    operations = [
        migrations.CreateModel(
            name='TrackingEvent',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(blank=True, max_length=50, null=True)),
                ('data', django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True)),
            ],
            options={
                'db_table': 'tracking_event',
            },
        ),
        migrations.CreateModel(
            name='TrackingVisit',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('ip_address', models.CharField(blank=True, max_length=64, null=True)),
            ],
            options={
                'db_table': 'tracking_visit',
            },
        ),
        migrations.CreateModel(
            name='TrackingVisitor',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('device_info', django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True)),
            ],
            options={
                'db_table': 'tracking_visitor',
            },
        ),
        migrations.RemoveField(
            model_name='visitorevents',
            name='visits',
        ),
        migrations.RemoveField(
            model_name='visits',
            name='visitor',
        ),
        migrations.DeleteModel(
            name='Visitor',
        ),
        migrations.DeleteModel(
            name='VisitorEvents',
        ),
        migrations.DeleteModel(
            name='Visits',
        ),
        migrations.AddField(
            model_name='trackingvisit',
            name='visitor',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tracking.TrackingVisitor'),
        ),
        migrations.AddField(
            model_name='trackingevent',
            name='visit',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tracking.TrackingVisit'),
        ),
    ]
