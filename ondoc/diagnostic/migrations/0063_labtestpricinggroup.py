# Generated by Django 2.0.5 on 2018-07-12 09:00

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0062_auto_20180712_1359'),
    ]

    operations = [
        migrations.CreateModel(
            name='LabTestPricingGroup',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
                'default_permissions': [],
            },
            bases=('diagnostic.labpricinggroup',),
        ),
    ]
