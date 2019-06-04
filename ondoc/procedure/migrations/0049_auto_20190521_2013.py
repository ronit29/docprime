# Generated by Django 2.0.5 on 2019-05-21 14:43

import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0254_merge_20190510_1419'),
        ('insurance', '0113_thirdpartyadministrator'),
        ('procedure', '0048_auto_20190521_1141'),
    ]

    operations = [
        migrations.AddField(
            model_name='ipdprocedurelead',
            name='alternate_number',
            field=models.BigIntegerField(blank=True, null=True, validators=[django.core.validators.MaxValueValidator(9999999999), django.core.validators.MinValueValidator(1000000000)]),
        ),
        migrations.AddField(
            model_name='ipdprocedurelead',
            name='hospital_reference_id',
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name='ipdprocedurelead',
            name='insurer',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='doctor.HealthInsuranceProvider'),
        ),
        migrations.AddField(
            model_name='ipdprocedurelead',
            name='num_of_chats',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='ipdprocedurelead',
            name='payment_amount',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True),
        ),
        migrations.AddField(
            model_name='ipdprocedurelead',
            name='payment_type',
            field=models.IntegerField(blank=True, choices=[(None, '--Select--'), (1, 'CASH'), (2, 'INSURANCE'), (3, 'GOVERNMENT_PANEL')], default=None, null=True),
        ),
        migrations.AddField(
            model_name='ipdprocedurelead',
            name='status',
            field=models.PositiveIntegerField(blank=True, choices=[(None, '--Select--'), (1, 'NEW'), (2, 'COST_REQUESTED'), (3, 'COST_SHARED'), (4, 'OPD'), (5, 'NOT_INTERESTED'), (6, 'COMPLETED')], default=None, null=True),
        ),
        migrations.AddField(
            model_name='ipdprocedurelead',
            name='tpa',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='insurance.ThirdPartyAdministrator'),
        ),
    ]