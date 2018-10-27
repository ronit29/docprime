# Generated by Django 2.0.5 on 2018-10-27 06:33

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('procedure', '0004_auto_20181026_1046'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProcedureToCategoryMapping',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('parent_category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='related_things_two', to='procedure.ProcedureCategory')),
            ],
            options={
                'db_table': 'procedure_to_category_mapping',
            },
        ),
        migrations.RemoveField(
            model_name='procedure',
            name='categories'
        ),
        migrations.AddField(
            model_name='procedure',
            name='categories',
            field=models.ManyToManyField(related_name='procedure', through='procedure.ProcedureToCategoryMapping',
                                         to='procedure.ProcedureCategory'),
        ),
        migrations.AddField(
            model_name='proceduretocategorymapping',
            name='procedure',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='related_things_one', to='procedure.Procedure'),
        ),
        migrations.AlterUniqueTogether(
            name='proceduretocategorymapping',
            unique_together={('procedure', 'parent_category')},
        ),
    ]
