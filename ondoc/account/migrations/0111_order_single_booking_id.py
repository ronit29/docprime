# Generated by Django 2.0.5 on 2019-11-18 08:46

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0110_auto_20191001_1618'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='single_booking',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='single_booking_order', to='account.Order'),
        ),
    ]
