# Generated by Django 2.0.5 on 2018-11-28 06:38

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0118_auto_20181030_1552'),
    ]

    operations = [
        migrations.AlterField(
            model_name='labappointment',
            name='insurance',
            field=models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='insurance.UserInsurance'),
        ),
    ]
