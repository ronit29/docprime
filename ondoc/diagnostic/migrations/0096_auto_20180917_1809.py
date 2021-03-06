# Generated by Django 2.0.5 on 2018-09-17 12:39

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0095_merge_20180914_1656'),
    ]

    operations = [
        migrations.CreateModel(
            name='ParameterLabTest',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('lab_test', models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to='diagnostic.LabTest')),
            ],
            options={
                'db_table': 'parameter_lab_test',
            },
        ),
        migrations.AlterField(
            model_name='testparameter',
            name='name',
            field=models.CharField(max_length=200, unique=True),
        ),
        migrations.AddField(
            model_name='parameterlabtest',
            name='parameter',
            field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to='diagnostic.TestParameter'),
        ),
        migrations.AlterUniqueTogether(
            name='parameterlabtest',
            unique_together={('parameter', 'lab_test')},
        ),
    ]
