# Generated by Django 2.0.5 on 2019-03-27 08:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('integrations', '0019_auto_20190326_1350'),
    ]

    operations = [
        migrations.AlterField(
            model_name='integratorhistory',
            name='status',
            field=models.PositiveSmallIntegerField(choices=[(1, 'Pushed and not accepted, Manage Manually'), (2, 'Pushed and accepted'), (3, 'Not pushed, Manage Manually'), (4, 'Cancel')], default=3),
        ),
    ]
