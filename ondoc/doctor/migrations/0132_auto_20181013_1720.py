# Generated by Django 2.0.5 on 2018-10-13 11:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0131_auto_20181013_1420'),
    ]

    operations = [
        migrations.AlterField(
            model_name='doctormobile',
            name='std_code',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
