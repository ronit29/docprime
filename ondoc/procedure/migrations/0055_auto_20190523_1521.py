# Generated by Django 2.0.5 on 2019-05-23 09:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('procedure', '0054_auto_20190523_1137'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ipdprocedurelead',
            name='status',
            field=models.PositiveIntegerField(blank=True, choices=[(None, '--Select--'), (1, 'NEW'), (2, 'COST_REQUESTED'), (3, 'COST_SHARED'), (4, 'OPD'), (7, 'VALID'), (8, 'CONTACTED'), (9, 'PLANNED'), (5, 'NOT_INTERESTED'), (6, 'COMPLETED')], default=1, null=True),
        ),
    ]
