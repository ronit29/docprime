# Generated by Django 2.0.5 on 2019-05-28 11:58

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('doctor', '0263_auto_20190528_1227'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='hospital',
            name='encrypted_hospital_id',
        ),
        migrations.RemoveField(
            model_name='hospital',
            name='encryption_hint',
        ),
        migrations.RemoveField(
            model_name='hospital',
            name='provider_encrypt',
        ),
        migrations.RemoveField(
            model_name='hospital',
            name='provider_encrypted_by',
        ),
        migrations.AddField(
            model_name='providerencrypt',
            name='encrypted_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='encrypted_hospitals', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='providerencrypt',
            name='encrypted_hospital_id',
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
        migrations.AddField(
            model_name='providerencrypt',
            name='hint',
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
        migrations.AddField(
            model_name='providerencrypt',
            name='is_encrypted',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='providerencrypt',
            name='is_valid',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='providerencrypt',
            name='is_consent_received',
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name='providerencrypt',
            name='phone_numbers',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.CharField(blank=True, max_length=10),
                                                            null=True, size=None),
        ),
    ]
