# Generated by Django 2.0.5 on 2019-06-27 06:26

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('insurance', '0141_userinsurance_cancel_customer_type'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='insurancetransaction',
            unique_together=set(),
        ),
    ]
