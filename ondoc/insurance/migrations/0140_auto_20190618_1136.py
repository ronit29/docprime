# Generated by Django 2.0.5 on 2019-06-18 06:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('insurance', '0139_auto_20190614_1952'),
    ]

    operations = [
        migrations.AddField(
            model_name='userinsurance',
            name='cancel_initial_date',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='userinsurance',
            name='cancel_status',
            field=models.PositiveIntegerField(choices=[(1, 'Non-Refunded'), (2, 'Refund-Initiate'), (3, 'Refunded')], default=1),
        ),
    ]
