# Generated by Django 2.0.5 on 2018-10-26 06:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0026_consumerrefund_refund_initiated_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='wallet_amount',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
    ]
