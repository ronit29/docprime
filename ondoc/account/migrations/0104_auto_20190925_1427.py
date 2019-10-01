# Generated by Django 2.0.5 on 2019-09-25 08:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0103_merge_20190905_1609'),
    ]

    operations = [
        migrations.AddField(
            model_name='pgtransaction',
            name='deleted',
            field=models.DateTimeField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name='pgtransaction',
            name='nodal_id',
            field=models.SmallIntegerField(blank=True, choices=[(1, 'Nodal 1'), (2, 'Nodal 2'), (3, 'Current Account')], null=True),
        ),
    ]
