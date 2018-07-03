# Generated by Django 2.0.5 on 2018-05-28 13:01

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0040_remove_doctor_hospitals'),
        ('authentication', '0015_address'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserPermission',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('permission', models.PositiveSmallIntegerField(choices=[(0, 'Read Appointment'), (1, 'Write Appointment'), (2, 'Add Appointment')])),
                ('doctor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.Doctor')),
                ('hospital', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='hospital_admins', to='doctor.Hospital')),
                ('hospital_network', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='network_admins', to='doctor.HospitalNetwork')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'user_permission',
            },
        ),
    ]