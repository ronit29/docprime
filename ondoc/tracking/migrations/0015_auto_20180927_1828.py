# Generated by Django 2.0.5 on 2018-09-27 12:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracking', '0014_auto_20180927_1801'),
    ]

    operations = [
        migrations.AlterField(
            model_name='serverhitmonitor',
            name='refferar',
            field=models.CharField(default=None, max_length=5000, null=True),
        ),
    ]
