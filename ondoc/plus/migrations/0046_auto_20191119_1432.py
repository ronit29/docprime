# Generated by Django 2.0.5 on 2019-11-19 09:02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('plus', '0045_merge_20191118_1115'),
    ]

    operations = [
        migrations.AlterField(
            model_name='plusmembers',
            name='address',
            field=models.TextField(default=None, null=True),
        ),
        migrations.AlterField(
            model_name='plusmembers',
            name='pincode',
            field=models.PositiveIntegerField(default=None, null=True),
        ),
    ]