# Generated by Django 2.0.5 on 2019-02-11 09:33

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0017_auto_20190211_1318'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='MatrixCity',
            new_name='MatrixMappedCity',
        ),
        migrations.RenameModel(
            old_name='MatrixState',
            new_name='MatrixMappedState',
        ),
        migrations.AlterModelTable(
            name='matrixmappedcity',
            table='matrix_mapped_city',
        ),
        migrations.AlterModelTable(
            name='matrixmappedstate',
            table='matrix_mapped_state',
        ),
    ]
