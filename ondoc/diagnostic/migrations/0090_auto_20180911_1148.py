# Generated by Django 2.0.5 on 2018-09-11 06:18

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0089_auto_20180911_1038'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='labtest',
            name='parameter',
        ),
        migrations.AddField(
            model_name='testparameter',
            name='lab_test',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='diagnostic.LabTest'),
        ),
    ]
