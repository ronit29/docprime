# Generated by Django 2.0.2 on 2018-04-18 05:36

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0011_auto_20180416_1610'),
    ]

    operations = [
        migrations.AddField(
            model_name='hospital',
            name='network',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='doctor.HospitalNetwork'),
        ),
        migrations.AlterField(
            model_name='hospitalnetworkmanager',
            name='contact_type',
            field=models.PositiveSmallIntegerField(choices=[(1, 'Other'), (2, 'Single Point of Contact'), (3, 'Manager')]),
        ),
    ]
