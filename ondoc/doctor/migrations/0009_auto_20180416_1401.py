# Generated by Django 2.0.2 on 2018-04-16 08:31

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0008_auto_20180416_0909'),
    ]

    operations = [
        migrations.CreateModel(
            name='HospitalNetworkEmail',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('email', models.EmailField(max_length=100)),
            ],
            options={
                'db_table': 'hospital_network_email',
            },
        ),
        migrations.CreateModel(
            name='HospitalNetworkHelpline',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('number', models.BigIntegerField()),
                ('details', models.CharField(blank=True, max_length=200)),
            ],
            options={
                'db_table': 'hospital_network_helpline',
            },
        ),
        migrations.CreateModel(
            name='HospitalNetworkManager',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=200)),
                ('number', models.BigIntegerField()),
                ('email', models.EmailField(blank=True, max_length=100)),
                ('details', models.CharField(blank=True, max_length=200)),
                ('contact_type', models.PositiveSmallIntegerField(blank=True, choices=[(1, 'Other'), (2, 'Single Point of Contact'), (3, 'Manager')], max_length=2, null=True)),
            ],
            options={
                'db_table': 'hospital_network_manager',
            },
        ),
        migrations.AlterField(
            model_name='hospitalnetwork',
            name='city',
            field=models.CharField(max_length=100),
        ),
        migrations.AlterField(
            model_name='hospitalnetwork',
            name='country',
            field=models.CharField(max_length=100),
        ),
        migrations.AlterField(
            model_name='hospitalnetwork',
            name='state',
            field=models.CharField(max_length=100),
        ),
        migrations.AddField(
            model_name='hospitalnetworkmanager',
            name='network',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.HospitalNetwork'),
        ),
        migrations.AddField(
            model_name='hospitalnetworkhelpline',
            name='network',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.HospitalNetwork'),
        ),
        migrations.AddField(
            model_name='hospitalnetworkemail',
            name='network',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.HospitalNetwork'),
        ),
    ]
