# Generated by Django 2.0.5 on 2019-05-28 06:57

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0262_providerencrypt'),
    ]

    operations = [
        migrations.AlterField(
            model_name='providerencrypt',
            name='hospital',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='encrypt_details', to='doctor.Hospital'),
        ),
    ]