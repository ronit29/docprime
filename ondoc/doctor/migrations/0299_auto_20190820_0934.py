# Generated by Django 2.0.5 on 2019-08-20 04:04

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0055_merge_20190711_1547'),
        ('doctor', '0298_hospitalnetworkimage'),
    ]

    operations = [
        migrations.CreateModel(
            name='HospitalNetworkServiceMapping',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('network', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='network_service_mappings', to='doctor.HospitalNetwork')),
                ('service', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='service_network_mappings', to='common.Service')),
            ],
            options={
                'db_table': 'hospital_network_service_mapping',
            },
        ),
        migrations.AlterField(
            model_name='hospitalnetworkimage',
            name='cover_image',
            field=models.BooleanField(default=False, verbose_name='Can be used as cover image?'),
        ),
        migrations.AlterUniqueTogether(
            name='hospitalnetworkservicemapping',
            unique_together={('network', 'service')},
        ),
    ]
