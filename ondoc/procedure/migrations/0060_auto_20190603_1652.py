# Generated by Django 2.0.5 on 2019-06-03 11:22

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('procedure', '0059_ipdcostestimateroomtypemapping_cost'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='ipdcostestimateroomtype',
            options={'verbose_name': 'Ipd Cost Estimate Room Type', 'verbose_name_plural': 'Ipd Cost Estimate Room Types'},
        ),
        migrations.AlterModelOptions(
            name='ipdprocedurecostestimate',
            options={'verbose_name': 'Ipd Cost Estimate', 'verbose_name_plural': 'Ipd Cost Estimate'},
        ),
        migrations.AddField(
            model_name='ipdprocedurelead',
            name='procedure_cost_estimates',
            field=models.ManyToManyField(related_name='hospital_cost_estimates', through='procedure.IpdProcedureLeadCostEstimateMapping', to='procedure.IpdProcedureCostEstimate'),
        ),
        migrations.AlterField(
            model_name='ipdcostestimateroomtypemapping',
            name='cost_estimate',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='room_type_costs', to='procedure.IpdProcedureCostEstimate'),
        ),
        migrations.AlterField(
            model_name='ipdcostestimateroomtypemapping',
            name='room_type',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='room', to='procedure.IpdCostEstimateRoomType'),
        ),
        migrations.AlterField(
            model_name='ipdprocedureleadcostestimatemapping',
            name='cost_estimate',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='procedure.IpdProcedureCostEstimate'),
        ),
    ]