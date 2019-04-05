# Generated by Django 2.0.5 on 2018-10-17 08:05

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('insurance', '0017_auto_20181017_1123'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='insurancetransaction',
            name='product_id',
        ),
        migrations.RemoveField(
            model_name='insurancetransaction',
            name='reference_id',
        ),
        migrations.RemoveField(
            model_name='userinsurance',
            name='product_id',
        ),
        migrations.AddField(
            model_name='insurancetransaction',
            name='amount',
            field=models.PositiveIntegerField(null=True),
        ),
        migrations.AddField(
            model_name='userinsurance',
            name='insurance_transaction',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='insurance.InsuranceTransaction'),
        ),
        migrations.AddField(
            model_name='userinsurance',
            name='insured_members',
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='insurancetransaction',
            name='order_id',
            field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to='account.Order'),
        ),
    ]
