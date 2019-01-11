# Generated by Django 2.0.5 on 2019-01-08 08:38

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0175_opdappointment_price_data'),
        ('web', '0020_onlinelead_source'),
    ]

    operations = [
        migrations.CreateModel(
            name='NonBookableDoctorLead',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(blank=True, max_length=255, null=True)),
                ('from_mobile', models.CharField(max_length=25)),
                ('to_mobile', models.CharField(max_length=25)),
                ('masked_mobile', models.CharField(blank=True, max_length=25, null=True)),
                ('matrix_lead_id', models.IntegerField(null=True)),
                ('source', models.CharField(default='docprimeNB', max_length=128)),
                ('doctor', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='doctor.Doctor')),
                ('hospital', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='doctor.Hospital')),
            ],
            options={
                'db_table': 'nb_doctor_lead',
            },
        ),
    ]