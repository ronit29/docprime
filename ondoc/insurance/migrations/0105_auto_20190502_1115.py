# Generated by Django 2.0.5 on 2019-05-02 05:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('insurance', '0104_auto_20190501_0011'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userinsurance',
            name='status',
            field=models.PositiveIntegerField(choices=[(1, 'Active'), (2, 'Cancelled'), (3, 'Expired'), (4, 'Onhold'), (5, 'Cancel Initiate')], default=1),
        ),
    ]
