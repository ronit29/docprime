# Generated by Django 2.0.5 on 2018-09-03 11:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0083_homepickupcharges'),
    ]

    operations = [
        migrations.AddField(
            model_name='labappointment',
            name='matrix_lead_id',
            field=models.IntegerField(null=True),
        ),
    ]
