# Generated by Django 2.0.5 on 2019-04-18 10:24

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0189_merge_20190412_2013'),
    ]

    operations = [
        migrations.AlterField(
            model_name='labappointment',
            name='money_pool',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='lab_apps', to='account.MoneyPool'),
        ),
    ]