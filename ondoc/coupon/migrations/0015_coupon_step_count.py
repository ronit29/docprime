# Generated by Django 2.0.5 on 2018-12-12 10:12

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('coupon', '0014_auto_20181129_1236'),
    ]

    operations = [
        migrations.AddField(
            model_name='coupon',
            name='step_count',
            field=models.PositiveIntegerField(blank=True, default=1, null=True, validators=[django.core.validators.MinValueValidator(1)],
                                              verbose_name='Valid only at multiples of this appointment number'),
        ),
        migrations.AddField(
            model_name='coupon',
            name='gender',
            field=models.CharField(blank=True, choices=[('m', 'Male'), ('f', 'Female'), ('o', 'Other')], default=None,
                                   max_length=1, null=True),
        ),
        migrations.AddField(
            model_name='coupon',
            name='age_end',
            field=models.PositiveIntegerField(blank=True, default=None, null=True,
                                              validators=[django.core.validators.MaxValueValidator(100),
                                                          django.core.validators.MinValueValidator(0)]),
        ),
        migrations.AddField(
            model_name='coupon',
            name='age_start',
            field=models.PositiveIntegerField(blank=True, default=None, null=True,
                                              validators=[django.core.validators.MaxValueValidator(100),
                                                          django.core.validators.MinValueValidator(0)]),
        ),
    ]
