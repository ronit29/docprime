# Generated by Django 2.0.5 on 2018-11-12 10:11

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('procedure', '0014_commonprocedurecategory'),
    ]

    operations = [
        migrations.AlterField(
            model_name='commonprocedurecategory',
            name='procedure',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='procedure.ProcedureCategory'),
        ),
    ]