# Generated by Django 2.0.5 on 2019-04-25 09:34

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('insurance', '0097_userinsurance_merchant_payout'),
    ]

    operations = [
        migrations.RenameField(
            model_name='insurer',
            old_name='transfer_premium_to',
            new_name='merchant',
        ),
    ]
