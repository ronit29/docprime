# Generated by Django 2.0.5 on 2018-09-20 09:31

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0115_auto_20180920_1426'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='commonspecialization',
            name='specialization',
        ),
        migrations.RemoveField(
            model_name='medicalcondition',
            name='specialization',
        ),
        migrations.RemoveField(
            model_name='medicalconditionspecialization',
            name='specialization',
        ),
    ]
