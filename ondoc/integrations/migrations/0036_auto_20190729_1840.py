# Generated by Django 2.0.5 on 2019-07-29 13:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('integrations', '0035_integratordoctormappings_integratorhospitalmappings'),
    ]

    operations = [
        migrations.AlterField(
            model_name='integratordoctormappings',
            name='integrator_hospital_id',
            field=models.PositiveIntegerField(null=True),
        ),
    ]
