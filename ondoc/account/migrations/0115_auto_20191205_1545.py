# Generated by Django 2.0.5 on 2019-12-05 10:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0114_merge_20191127_1822'),
    ]

    operations = [
        migrations.AddField(
            model_name='consumerrefund',
            name='bankRefNum',
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name='consumerrefund',
            name='bank_arn',
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name='consumerrefund',
            name='refundDate',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='consumerrefund',
            name='refundId',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
