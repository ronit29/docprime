# Generated by Django 2.0.5 on 2018-11-13 04:55

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0158_doctorclinic_enabled_for_online_booking'),
    ]

    operations = [
        migrations.AlterField(
            model_name='doctorclinic',
            name='hospital',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='hospital_doctors', to='doctor.Hospital'),
        ),
    ]
