# Generated by Django 2.0.5 on 2019-03-28 08:01

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('procedure', '0030_auto_20190328_1329'),
    ]

    operations = [
        migrations.AddField(
            model_name='ipdproceduredetail',
            name='ipd_procedure',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='procedure.IpdProcedure', verbose_name='IPD Procedure'),
        ),
    ]
