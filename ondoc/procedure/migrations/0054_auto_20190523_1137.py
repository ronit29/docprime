# Generated by Django 2.0.5 on 2019-05-23 06:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('procedure', '0053_auto_20190522_1318'),
    ]

    operations = [
        migrations.AddField(
            model_name='ipdprocedurelead',
            name='planned_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='ipdprocedurelead',
            name='status',
            field=models.PositiveIntegerField(blank=True, choices=[(None, '--Select--'), (1, 'NEW'), (2, 'COST_REQUESTED'), (3, 'COST_SHARED'), (4, 'OPD'), (7, 'valid'), (8, 'contacted'), (9, 'planned'), (5, 'NOT_INTERESTED'), (6, 'COMPLETED')], default=1, null=True),
        ),
    ]
