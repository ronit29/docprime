# Generated by Django 2.0.5 on 2019-05-13 12:59

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('doctor', '0253_auto_20190509_1509'),
    ]

    operations = [
        migrations.AddField(
            model_name='hospital',
            name='provider_encrypt',
            field=models.NullBooleanField(),
        ),
        migrations.AddField(
            model_name='hospital',
            name='provider_encrypted_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='encrypted_hospitals', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='patientmobile',
            name='encrypted_number',
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
    ]