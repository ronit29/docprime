# Generated by Django 2.0.5 on 2019-08-27 11:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0221_merge_20190816_1138'),
    ]

    operations = [
        migrations.AddField(
            model_name='labappointment',
            name='spo_lead_id',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
