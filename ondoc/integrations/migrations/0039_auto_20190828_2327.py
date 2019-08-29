# Generated by Django 2.0.5 on 2019-08-28 17:57

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('integrations', '0038_auto_20190827_1043'),
    ]

    operations = [
        migrations.CreateModel(
            name='IntegratorCity',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('city_name', models.CharField(blank=True, max_length=60, null=True)),
                ('city_id', models.IntegerField(blank=True, null=True)),
            ],
            options={
                'db_table': 'integrator_city',
            },
        ),
        migrations.CreateModel(
            name='IntegratorTestCityMapping',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('integrator_city', models.ForeignKey(null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='integrations.IntegratorCity')),
            ],
            options={
                'db_table': 'integrator_test_city_mapping',
            },
        ),
        migrations.RemoveField(
            model_name='integratortestmapping',
            name='integrator_city',
        ),
        migrations.RemoveField(
            model_name='integratortestmapping',
            name='integrator_city_id',
        ),
        migrations.AddField(
            model_name='integratortestcitymapping',
            name='integrator_test_mapping',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='integrations.IntegratorTestMapping'),
        ),
    ]
