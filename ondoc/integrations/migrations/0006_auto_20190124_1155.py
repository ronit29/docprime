# Generated by Django 2.0.5 on 2019-01-24 06:25

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('integrations', '0005_integratorproductdetail'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='integratorproductdetail',
            name='integrator',
        ),
        migrations.AddField(
            model_name='integratormapping',
            name='integrator_product_data',
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='integratormapping',
            name='integrator_test_name',
            field=models.CharField(default=None, max_length=60),
        ),
        migrations.DeleteModel(
            name='IntegratorProductDetail',
        ),
    ]