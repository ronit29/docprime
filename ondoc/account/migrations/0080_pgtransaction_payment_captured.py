# Generated by Django 2.0.5 on 2019-07-16 12:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0079_merge_20190716_1632'),
    ]

    operations = [
        migrations.AddField(
            model_name='pgtransaction',
            name='payment_captured',
            field=models.BooleanField(default=False),
        ),
    ]
