# Generated by Django 2.0.5 on 2018-12-03 14:23

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0032_dummytransactions'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pgtransaction',
            name='order_id',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='txn', to='account.Order'),
        ),
    ]
