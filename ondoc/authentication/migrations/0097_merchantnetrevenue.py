# Generated by Django 2.0.5 on 2019-06-18 08:12

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0096_merchant_enable_for_tds_deduction'),
    ]

    operations = [
        migrations.CreateModel(
            name='MerchantNetRevenue',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('totol_revenue', models.DecimalField(blank=True, decimal_places=2, default=None, max_digits=10, null=True)),
                ('financial_year', models.CharField(blank=True, max_length=20, null=True)),
                ('merchant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='net_revenue', to='authentication.Merchant')),
            ],
            options={
                'db_table': 'merchant_net_revenue',
            },
        ),
    ]
