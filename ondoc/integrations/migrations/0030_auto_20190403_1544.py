# Generated by Django 2.0.5 on 2019-04-03 10:14

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0181_auto_20190403_1544'),
        ('integrations', '0029_integratortestparameter_response_data'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='IntegratorTestParameter',
            new_name='IntegratorTestParameterMapping',
        ),
        migrations.RenameField(
            model_name='integratortestparametermapping',
            old_name='test_parameter_new',
            new_name='test_parameter_chat',
        ),
        migrations.AlterModelTable(
            name='integratortestparametermapping',
            table='integrator_test_parameter_mapping',
        ),
    ]
