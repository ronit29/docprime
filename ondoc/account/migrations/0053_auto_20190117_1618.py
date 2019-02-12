# Generated by Django 2.0.5 on 2019-01-17 10:48

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('cart', '0001_initial'),
        ('account', '0052_remove_moneypool_user'),
    ]

    operations = [
        migrations.AddField(
            model_name='moneypool',
            name='logs',
            field=django.contrib.postgres.fields.jsonb.JSONField(default=[]),
        ),
        migrations.AddField(
            model_name='order',
            name='cart',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='order', to='cart.Cart'),
        ),
    ]
