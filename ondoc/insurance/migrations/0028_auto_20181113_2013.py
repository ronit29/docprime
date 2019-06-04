# Generated by Django 2.0.5 on 2018-11-13 14:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('insurance', '0027_merge_20181023_1826'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='insurerfloat',
            name='max_float',
        ),
        migrations.AddField(
            model_name='insurer',
            name='max_float',
            field=models.PositiveIntegerField(default=None),
        ),
        migrations.AddField(
            model_name='insurer',
            name='min_float',
            field=models.PositiveIntegerField(default=None),
        ),
        migrations.AlterField(
            model_name='insurancetransaction',
            name='amount',
            field=models.PositiveIntegerField(default=None),
        ),
        migrations.AlterField(
            model_name='insurerfloat',
            name='current_float',
            field=models.PositiveIntegerField(default=None),
        ),
    ]