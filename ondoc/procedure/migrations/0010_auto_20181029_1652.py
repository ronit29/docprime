# Generated by Django 2.0.5 on 2018-10-29 11:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('procedure', '0009_procedurecategory_is_live'),
    ]

    operations = [
        migrations.AlterField(
            model_name='procedure',
            name='categories',
            field=models.ManyToManyField(related_name='procedures', through='procedure.ProcedureToCategoryMapping', to='procedure.ProcedureCategory'),
        ),
    ]
