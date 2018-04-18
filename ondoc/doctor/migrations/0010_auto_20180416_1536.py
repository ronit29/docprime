# Generated by Django 2.0.2 on 2018-04-16 10:06

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0009_auto_20180416_1401'),
    ]

    operations = [
        migrations.CreateModel(
            name='HospitalNetworkMapping',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'hospital_network_mapping',
            },
        ),
        migrations.AlterUniqueTogether(
            name='hospitalclinicalspeciality',
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name='hospitalclinicalspeciality',
            name='hospital',
        ),
        migrations.RemoveField(
            model_name='hospitalclinicalspeciality',
            name='speciality',
        ),
        migrations.AlterField(
            model_name='hospital',
            name='city',
            field=models.CharField(max_length=100),
        ),
        migrations.AlterField(
            model_name='hospital',
            name='country',
            field=models.CharField(max_length=100),
        ),
        migrations.AlterField(
            model_name='hospital',
            name='state',
            field=models.CharField(max_length=100),
        ),
        migrations.AlterField(
            model_name='hospitalnetworkmanager',
            name='contact_type',
            field=models.PositiveSmallIntegerField(choices=[(1, 'Other'), (2, 'Single Point of Contact'), (3, 'Manager')], default=1, max_length=2),
            preserve_default=False,
        ),
        migrations.DeleteModel(
            name='ClinicalSpeciality',
        ),
        migrations.DeleteModel(
            name='HospitalClinicalSpeciality',
        ),
        migrations.AddField(
            model_name='hospitalnetworkmapping',
            name='hospital',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.Hospital'),
        ),
        migrations.AddField(
            model_name='hospitalnetworkmapping',
            name='network',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.HospitalNetwork'),
        ),
    ]
