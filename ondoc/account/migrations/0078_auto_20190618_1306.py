# Generated by Django 2.0.5 on 2019-06-18 07:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0077_merge_20190617_1837'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pgtransaction',
            name='transaction_id',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
