# Generated by Django 2.0.5 on 2019-10-09 10:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('plus', '0032_auto_20191007_1546'),
    ]

    operations = [
        migrations.AddField(
            model_name='plusplans',
            name='price_criteria',
            field=models.CharField(choices=[('AGREED_PRICE', 'AGREED_PRICE'), ('COD_DEAL_PRICE', 'COD_DEAL_PRICE'), ('DEAL_PRICE', 'DEAL_PRICE'), ('MRP', 'MRP')], max_length=100, null=True),
        ),
    ]
