# Generated by Django 2.0.5 on 2019-04-04 14:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0067_auto_20190326_1349'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='reference_id',
            field=models.BigIntegerField(blank=True, null=True),
        ),
    ]
