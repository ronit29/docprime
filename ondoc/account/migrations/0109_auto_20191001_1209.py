# Generated by Django 2.0.5 on 2019-10-01 06:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0108_consumertransaction_ref_txns'),
    ]

    operations = [
        migrations.AlterField(
            model_name='consumertransaction',
            name='balance',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10, null=True),
        ),
    ]
