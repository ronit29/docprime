# Generated by Django 2.0.5 on 2018-12-03 14:23

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0033_auto_20181203_1953'),
    ]

    operations = [
        migrations.RenameField(
            model_name='pgtransaction',
            old_name='order_id',
            new_name='order',
        ),
    ]
