# Generated by Django 2.0.5 on 2018-09-27 05:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracking', '0010_serverhitmonitor'),
    ]

    operations = [
        migrations.AlterField(
            model_name='serverhitmonitor',
            name='refferar',
            field=models.CharField(default=None, max_length=255, null=True),
        ),
    ]
