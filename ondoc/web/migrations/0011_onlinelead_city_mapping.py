# Generated by Django 2.0.5 on 2018-09-03 09:09

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0001_initial'),
        ('web', '0010_auto_20180829_1842'),
    ]

    operations = [
        migrations.AddField(
            model_name='onlinelead',
            name='city_mapping',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='common.Cities'),
        ),
    ]