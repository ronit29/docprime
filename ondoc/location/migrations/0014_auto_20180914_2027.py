# Generated by Django 2.0.5 on 2018-09-14 14:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('location', '0013_auto_20180914_1657'),
    ]

    operations = [
        migrations.AlterField(
            model_name='entityaddress',
            name='type',
            field=models.CharField(choices=[('ADMINISTRATIVE_AREA_LEVEL_1', 'ADMINISTRATIVE_AREA_LEVEL_1'), ('ADMINISTRATIVE_AREA_LEVEL_2', 'ADMINISTRATIVE_AREA_LEVEL_2'), ('COUNTRY', 'COUNTRY'), ('LOCALITY', 'LOCALITY'), ('SUBLOCALITY', 'SUBLOCALITY')], max_length=128),
        ),
        migrations.AlterField(
            model_name='entitylocationrelationship',
            name='type',
            field=models.CharField(choices=[('ADMINISTRATIVE_AREA_LEVEL_1', 'ADMINISTRATIVE_AREA_LEVEL_1'), ('ADMINISTRATIVE_AREA_LEVEL_2', 'ADMINISTRATIVE_AREA_LEVEL_2'), ('COUNTRY', 'COUNTRY'), ('LOCALITY', 'LOCALITY'), ('SUBLOCALITY', 'SUBLOCALITY')], max_length=128),
        ),
    ]