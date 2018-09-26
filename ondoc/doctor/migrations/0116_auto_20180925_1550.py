# Generated by Django 2.0.5 on 2018-09-25 10:20

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0115_auto_20180925_1233'),
    ]

    operations = [
        migrations.CreateModel(
            name='DoctorClinicProcedure',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('mrp', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('agreed_price', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('listing_price', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('doctor_clinic', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.DoctorClinic')),
            ],
            options={
                'db_table': 'doctor_clinic_procedure',
            },
        ),
        migrations.CreateModel(
            name='Procedure',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=500, unique=True)),
                ('details', models.CharField(max_length=2000)),
                ('duration', models.IntegerField()),
            ],
            options={
                'db_table': 'procedure',
            },
        ),
        migrations.AlterUniqueTogether(
            name='doctorprocedure',
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name='doctorprocedure',
            name='doctor',
        ),
        migrations.RemoveField(
            model_name='doctorprocedure',
            name='hospital',
        ),
        migrations.DeleteModel(
            name='DoctorProcedure',
        ),
        migrations.AddField(
            model_name='doctorclinicprocedure',
            name='procedure',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.Procedure'),
        ),
        migrations.AlterUniqueTogether(
            name='doctorclinicprocedure',
            unique_together={('procedure', 'doctor_clinic')},
        ),
    ]