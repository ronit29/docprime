# Generated by Django 2.0.6 on 2018-07-05 10:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0009_auto_20180625_1414'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pgtransaction',
            name='response_code',
            field=models.CharField(max_length=50),
        ),
    ]
