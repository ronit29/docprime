# Generated by Django 2.0.5 on 2019-05-03 12:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0201_auto_20190503_1708'),
    ]

    operations = [
        migrations.AlterField(
            model_name='labtestthresholds',
            name='gender',
            field=models.CharField(blank=True, choices=[('m', 'Male'), ('f', 'Female'), ('o', 'Other'), ('', 'Null')], default=None, max_length=50, null=True),
        ),
    ]