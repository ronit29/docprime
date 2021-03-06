# Generated by Django 2.0.5 on 2019-11-22 11:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0111_consumertransaction_deleted'),
    ]

    operations = [
        migrations.AlterField(
            model_name='merchantpayout',
            name='status',
            field=models.PositiveIntegerField(choices=[(1, 'Pending'), (2, 'ATTEMPTED'), (3, 'Paid'), (4, 'Initiated'), (5, 'In Process'), (6, 'Failed from Queue'), (7, 'Failed from Detail'), (8, 'Archive')], default=1),
        ),
    ]
