# Generated by Django 2.0.5 on 2018-07-10 09:04

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0068_doctor_about'),
    ]

    operations = [
        migrations.CreateModel(
            name='AboutDoctor',
            fields=[
            ],
            options={
                'proxy': True,
                'default_permissions': [],
                'indexes': [],
            },
            bases=('doctor.doctor',),
        ),
    ]
