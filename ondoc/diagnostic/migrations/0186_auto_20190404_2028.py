# Generated by Django 2.0.5 on 2019-04-04 14:58

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0185_auto_20190404_2025'),
    ]

    operations = [
        migrations.AlterField(
            model_name='labappointment',
            name='insurance',
            field=models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='insurance.UserInsurance'),
        ),
    ]
