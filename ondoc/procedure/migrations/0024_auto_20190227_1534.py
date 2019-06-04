# Generated by Django 2.0.5 on 2019-02-27 10:04

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('procedure', '0023_auto_20190227_1115'),
    ]

    operations = [
        migrations.CreateModel(
            name='CommonIpdProcedure',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('priority', models.PositiveIntegerField(default=0)),
            ],
            options={
                'db_table': 'common_ipd_procedure',
            },
        ),
        migrations.RenameField(
            model_name='ipdprocedure',
            old_name='is_live',
            new_name='is_enabled',
        ),
        migrations.AddField(
            model_name='commonipdprocedure',
            name='ipd_procedure',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='procedure.IpdProcedure'),
        ),
    ]