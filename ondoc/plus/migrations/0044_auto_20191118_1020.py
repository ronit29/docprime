# Generated by Django 2.0.5 on 2019-11-18 04:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('plus', '0043_tempplususer_profile'),
    ]

    operations = [
        migrations.AlterField(
            model_name='plusmembers',
            name='city',
            field=models.CharField(blank=True, default=None, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name='plusmembers',
            name='district',
            field=models.CharField(blank=True, default=None, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name='plusmembers',
            name='state',
            field=models.CharField(blank=True, default=None, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name='plusmembers',
            name='state_code',
            field=models.CharField(blank=True, default=None, max_length=10, null=True),
        ),
    ]