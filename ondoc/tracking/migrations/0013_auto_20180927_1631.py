# Generated by Django 2.0.5 on 2018-09-27 11:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracking', '0012_serverhitmonitor_ip_address'),
    ]

    operations = [
        migrations.AlterField(
            model_name='serverhitmonitor',
            name='ip_address',
            field=models.CharField(default=None, max_length=255, null=True),
        ),
    ]