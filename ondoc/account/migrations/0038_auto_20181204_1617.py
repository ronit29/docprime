# Generated by Django 2.0.5 on 2018-12-04 10:47

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0037_auto_20181204_1616'),
    ]

    operations = [
        migrations.AlterField(
            model_name='merchantpayout',
            name='paid_to',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='payouts', to='authentication.Merchant'),
        ),
    ]
