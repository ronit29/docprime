# Generated by Django 2.0.5 on 2018-07-03 08:57

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('doctor', '0062_auto_20180703_1405'),
    ]

    operations = [
        migrations.AddField(
            model_name='hospitalnetwork',
            name='assigned_to',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_hospital_networks', to=settings.AUTH_USER_MODEL),
        ),
    ]
