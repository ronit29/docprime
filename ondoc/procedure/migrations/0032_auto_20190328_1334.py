# Generated by Django 2.0.5 on 2019-03-28 08:04

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('procedure', '0031_ipdproceduredetail_ipd_procedure'),
    ]

    operations = [
        migrations.RenameField(
            model_name='ipdproceduredetail',
            old_name='type',
            new_name='detail_type',
        ),
    ]