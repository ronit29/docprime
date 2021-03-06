# Generated by Django 2.0.5 on 2020-02-10 12:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0345_auto_20200205_1816'),
    ]

    operations = [
        migrations.AlterField(
            model_name='googlemaprecords',
            name='digital_only_report',
            field=models.SmallIntegerField(choices=[(1, 'NA'), (2, 'Yes'), (3, 'No'), (4, 'Maybe')], default=1),
        ),
        migrations.AlterField(
            model_name='googlemaprecords',
            name='has_phlebo',
            field=models.SmallIntegerField(choices=[(1, 'NA'), (2, 'In Clinic'), (3, 'On Lab/Meddo Payroll'), (4, 'On Call'), (5, 'No Phlebo')], default=1),
        ),
        migrations.AlterField(
            model_name='googlemaprecords',
            name='interested_in_diagnostics',
            field=models.SmallIntegerField(choices=[(1, 'NA'), (2, 'Yes'), (3, 'No'), (4, 'Maybe')], default=1),
        ),
        migrations.AlterField(
            model_name='googlemaprecords',
            name='interested_in_pharmacy',
            field=models.SmallIntegerField(choices=[(1, 'NA'), (2, 'Yes'), (3, 'No'), (4, 'Maybe')], default=1),
        ),
        migrations.AlterField(
            model_name='googlemaprecords',
            name='onboarded',
            field=models.SmallIntegerField(choices=[(1, 'NA'), (2, 'Yes'), (3, 'No'), (4, 'Maybe')], default=1),
        ),
        migrations.AlterField(
            model_name='googlemaprecords',
            name='ready_to_use_wallet',
            field=models.SmallIntegerField(choices=[(1, 'NA'), (2, 'Yes'), (3, 'No'), (4, 'Maybe')], default=1),
        ),
    ]
