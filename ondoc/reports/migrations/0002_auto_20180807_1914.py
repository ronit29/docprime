# Generated by Django 2.0.5 on 2018-08-07 13:44

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('reports', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='GeneratedReport',
            fields=[
            ],
            options={
                'proxy': True,
                'default_permissions': [],
                'indexes': [],
            },
            bases=('reports.report',),
        ),
        migrations.AlterModelTable(
            name='report',
            table='report',
        ),
    ]