# Generated by Django 2.0.5 on 2018-05-29 05:01

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0016_userpermission'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userpermission',
            name='doctor',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='doctor.Doctor'),
        ),
        migrations.AlterField(
            model_name='userpermission',
            name='hospital',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='hospital_admins', to='doctor.Hospital'),
        ),
        migrations.AlterField(
            model_name='userpermission',
            name='hospital_network',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='network_admins', to='doctor.HospitalNetwork'),
        ),
        migrations.AlterField(
            model_name='userpermission',
            name='permission',
            field=models.PositiveSmallIntegerField(choices=[(0, 'Read Appointment'), (1, 'Write Appointment')]),
        ),
    ]
