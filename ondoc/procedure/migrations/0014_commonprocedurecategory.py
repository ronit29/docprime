# Generated by Django 2.0.5 on 2018-11-12 09:29

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('procedure', '0013_auto_20181105_1019'),
    ]

    operations = [
        migrations.CreateModel(
            name='CommonProcedureCategory',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('priority', models.PositiveIntegerField(default=0)),
                ('procedure', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='procedure.Procedure')),
            ],
            options={
                'db_table': 'common_procedure_category',
            },
        ),
    ]
