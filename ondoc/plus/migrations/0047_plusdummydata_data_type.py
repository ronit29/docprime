# Generated by Django 2.0.5 on 2019-11-21 05:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('plus', '0046_auto_20191119_1432'),
    ]

    operations = [
        migrations.AddField(
            model_name='plusdummydata',
            name='data_type',
            field=models.CharField(choices=[('PLAN_PURCHASE', 'PLAN_PURCHASE'), ('SINGLE_PURCHASE', 'SINGLE_PURCHASE')], max_length=100, null=True),
        ),
    ]