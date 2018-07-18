# Generated by Django 2.0.6 on 2018-07-16 05:09

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0013_auto_20180713_2151'),
    ]

    operations = [
        migrations.AlterField(
            model_name='consumerrefund',
            name='pg_transaction',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='pg_refund', to='account.PgTransaction'),
        ),
        migrations.AlterField(
            model_name='pgtransaction',
            name='transaction_date',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
