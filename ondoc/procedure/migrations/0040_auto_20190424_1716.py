# Generated by Django 2.0.5 on 2019-04-24 11:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('procedure', '0039_auto_20190424_1537'),
    ]

    operations = [
        migrations.RenameField(
            model_name='ipdproceduresynonymmapping',
            old_name='ipd_procedure',
            new_name='ipd_procedure_id',
        ),
        migrations.RenameField(
            model_name='ipdproceduresynonymmapping',
            old_name='ipd_procedure_synonym',
            new_name='ipd_procedure_synonym_id',
        ),
        migrations.AlterField(
            model_name='ipdproceduresynonym',
            name='name',
            field=models.CharField(default='', max_length=1000),
        ),
    ]
