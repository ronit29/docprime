# Generated by Django 2.0.5 on 2019-05-23 12:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0073_auto_20190425_1949'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pgtransaction',
            name='transaction_id',
            field=models.CharField(blank=True, max_length=100, unique=True),
        ),
    ]