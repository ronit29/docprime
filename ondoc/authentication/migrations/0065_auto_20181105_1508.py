# Generated by Django 2.0.5 on 2018-11-05 09:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0064_spocdetails_source'),
    ]

    operations = [
        migrations.AddField(
            model_name='genericadmin',
            name='name',
            field=models.CharField(blank=True, max_length=24, null=True),
        ),
        migrations.AlterField(
            model_name='genericadmin',
            name='permission_type',
            field=models.PositiveSmallIntegerField(choices=[(3, 'All'), (1, 'Appointment'), (2, 'Billing')], default=1, max_length=20),
        ),
    ]
