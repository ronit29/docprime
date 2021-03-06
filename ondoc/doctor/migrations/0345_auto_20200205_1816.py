# Generated by Django 2.0.5 on 2020-02-05 12:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0344_googlemaprecords_onboarded'),
    ]

    operations = [
        migrations.AddField(
            model_name='googlemaprecords',
            name='cluster',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='googlemaprecords',
            name='digital_only_report',
            field=models.SmallIntegerField(choices=[(1, 'NA'), (2, 'Yes'), (3, 'No')], default=1),
        ),
        migrations.AddField(
            model_name='googlemaprecords',
            name='interested_in_diagnostics',
            field=models.SmallIntegerField(choices=[(1, 'NA'), (2, 'Yes'), (3, 'No')], default=1),
        ),
        migrations.AddField(
            model_name='googlemaprecords',
            name='interested_in_pharmacy',
            field=models.SmallIntegerField(choices=[(1, 'NA'), (2, 'Yes'), (3, 'No')], default=1),
        ),
        migrations.AddField(
            model_name='googlemaprecords',
            name='latitude_sales',
            field=models.DecimalField(blank=True, decimal_places=6, default=None, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name='googlemaprecords',
            name='longitude_sales',
            field=models.DecimalField(blank=True, decimal_places=6, default=None, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name='googlemaprecords',
            name='phlebo_type',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='googlemaprecords',
            name='ready_to_use_wallet',
            field=models.SmallIntegerField(choices=[(1, 'NA'), (2, 'Yes'), (3, 'No')], default=1),
        ),
        migrations.AddField(
            model_name='googlemaprecords',
            name='samples_per_month',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
