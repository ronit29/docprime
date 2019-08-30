# Generated by Django 2.0.5 on 2019-08-20 07:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0055_merge_20190711_1547'),
        ('doctor', '0302_hospitalnetwork_always_open'),
    ]

    operations = [
        migrations.AddField(
            model_name='hospitalnetwork',
            name='service',
            field=models.ManyToManyField(related_name='of_hospital_network', through='doctor.HospitalNetworkServiceMapping', to='common.Service'),
        ),
    ]
