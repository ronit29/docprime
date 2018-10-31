# Generated by Django 2.0.5 on 2018-10-27 06:49

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('procedure', '0005_auto_20181027_1203'),
    ]

    operations = [
        migrations.AlterField(
            model_name='proceduretocategorymapping',
            name='parent_category',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='procedures_mapping', to='procedure.ProcedureCategory'),
        ),
        migrations.AlterField(
            model_name='proceduretocategorymapping',
            name='procedure',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='parent_categories_mapping', to='procedure.Procedure'),
        ),
    ]