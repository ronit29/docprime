# Generated by Django 2.0.5 on 2019-11-29 11:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0333_auto_20191128_1155'),
    ]

    operations = [
        migrations.AddField(
            model_name='commonhospital',
            name='percentage',
            field=models.FloatField(blank=True, null=True),
        ),
    ]
