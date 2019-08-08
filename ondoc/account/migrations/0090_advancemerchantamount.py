# Generated by Django 2.0.5 on 2019-07-24 07:38

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0108_merge_20190718_1833'),
        ('account', '0089_advancemerchantpayout'),
    ]

    operations = [
        migrations.CreateModel(
            name='AdvanceMerchantAmount',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('amount', models.DecimalField(blank=True, decimal_places=2, default=None, max_digits=10, null=True)),
                ('merchant', models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to='authentication.Merchant')),
            ],
            options={
                'db_table': 'advance_merchant_amount',
            },
        ),
    ]
