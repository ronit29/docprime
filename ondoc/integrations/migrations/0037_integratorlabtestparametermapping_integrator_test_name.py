# Generated by Django 2.0.5 on 2019-08-05 11:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('integrations', '0036_auto_20190805_1552'),
    ]

    operations = [
        migrations.AddField(
            model_name='integratorlabtestparametermapping',
            name='integrator_test_name',
            field=models.CharField(blank=True, max_length=100, null=True, unique=True),
        ),
    ]