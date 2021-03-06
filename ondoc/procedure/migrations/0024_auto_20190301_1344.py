# Generated by Django 2.0.5 on 2019-03-01 08:14

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('procedure', '0023_auto_20190227_1115'),
    ]

    operations = [
        migrations.CreateModel(
            name='IpdProcedureCategory',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('search_key', models.CharField(blank=True, max_length=256, null=True)),
                ('name', models.CharField(max_length=500)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='IpdProcedureCategoryMapping',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ipd_procedures_mappings', to='procedure.IpdProcedureCategory')),
                ('ipd_procedure', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ipd_category_mappings', to='procedure.IpdProcedure')),
            ],
            options={
                'db_table': 'ipd_procedure_category_mapping',
            },
        ),
        migrations.AlterUniqueTogether(
            name='ipdprocedurecategorymapping',
            unique_together={('ipd_procedure', 'category')},
        ),
    ]
