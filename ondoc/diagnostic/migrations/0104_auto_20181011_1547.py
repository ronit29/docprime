# Generated by Django 2.0.5 on 2018-10-11 10:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0103_lab_priority'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lab',
            name='priority',
            field=models.IntegerField(blank=True, default=0, null=True),
        ),
    ]
