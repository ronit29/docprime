# Generated by Django 2.0.6 on 2018-07-06 13:43

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('payout', '0002_auto_20180630_1952'),
        ('doctor', '0059_auto_20180702_1849'),
    ]

    operations = [
        migrations.AddField(
            model_name='opdappointment',
            name='outstanding',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='payout.Outstanding'),
        ),
    ]
