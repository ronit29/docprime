# Generated by Django 2.0.5 on 2019-06-24 13:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('insurance', '0142_userinsurance_cancel_initiate_by'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userinsurance',
            name='status',
            field=models.PositiveIntegerField(choices=[(1, 'Active'), (2, 'Cancelled'), (3, 'Expired'), (4, 'Onhold'), (5, 'Cancel Initiate'), (6, 'Cancellation Approved')], default=1),
        ),
    ]
