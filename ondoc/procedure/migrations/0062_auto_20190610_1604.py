# Generated by Django 2.0.5 on 2019-06-10 10:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('procedure', '0061_auto_20190603_1731'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ipdprocedurecostestimate',
            name='stay_duration',
            field=models.IntegerField(default=1),
        ),
    ]