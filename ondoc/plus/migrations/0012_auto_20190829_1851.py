# Generated by Django 2.0.5 on 2019-08-29 13:21

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('plus', '0011_plusplanparameters_plusplanparametersmapping'),
    ]

    operations = [
        migrations.AlterField(
            model_name='plusplanparametersmapping',
            name='plus_plan',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='plan_parameters', to='plus.PlusPlans'),
        ),
    ]