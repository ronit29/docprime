# Generated by Django 2.0.5 on 2019-01-25 09:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0191_auto_20190124_1845'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cancellationreason',
            name='type',
            field=models.PositiveSmallIntegerField(blank=True, default=None, null=True),
        ),
    ]
