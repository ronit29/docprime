# Generated by Django 2.0.2 on 2018-06-25 08:21

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0047_auto_20180613_1214'),
    ]

    operations = [
        migrations.CreateModel(
            name='DoctorSpecialization',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('doctor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='doctorspecializations', to='doctor.Doctor')),
                ('specialization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.Specialization')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
