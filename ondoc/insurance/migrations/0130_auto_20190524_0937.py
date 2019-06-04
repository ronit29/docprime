# Generated by Django 2.0.5 on 2019-05-24 04:07

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('insurance', '0129_auto_20190523_2258'),
    ]

    operations = [
        migrations.AlterField(
            model_name='insurerpolicynumber',
            name='insurance_plan',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='plan_policy_number', to='insurance.InsurancePlans'),
        ),
        migrations.AlterField(
            model_name='insurerpolicynumber',
            name='insurer',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='policy_number_history', to='insurance.Insurer'),
        ),
    ]