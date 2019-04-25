# Generated by Django 2.0.5 on 2019-04-25 07:41

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0069_auto_20190411_1250'),
        ('insurance', '0096_insurer_transfer_premium_to'),
    ]

    operations = [
        migrations.AddField(
            model_name='userinsurance',
            name='merchant_payout',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='user_insurance', to='account.MerchantPayout'),
        ),
    ]
