# Generated by Django 2.0.5 on 2019-08-29 06:06

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('plus', '0008_auto_20190829_1136'),
        ('doctor', '0305_auto_20190828_1717'),
    ]

    operations = [
        migrations.AddField(
            model_name='opdappointment',
            name='plus_plan',
            field=models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='plus.PlusUser'),
        ),
    ]