# Generated by Django 2.0.5 on 2018-10-26 07:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0026_consumerrefund_refund_initiated_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='matrix_lead_id',
            field=models.PositiveIntegerField(null=True),
        ),
    ]
