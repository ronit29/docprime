# Generated by Django 2.0.5 on 2018-09-17 10:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('location', '0014_auto_20180914_2027'),
    ]

    operations = [
        migrations.AlterField(
            model_name='entityaddress',
            name='type',
            field=models.CharField(choices=[('ADMINISTRATIVE_AREA_LEVEL_1', 'ADMINISTRATIVE_AREA_LEVEL_1'), ('ADMINISTRATIVE_AREA_LEVEL_2', 'ADMINISTRATIVE_AREA_LEVEL_2'), ('COUNTRY', 'COUNTRY'), ('LOCALITY', 'LOCALITY'), ('POSTAL_CODE', 'POSTAL_CODE'), ('SUBLOCALITY', 'SUBLOCALITY')], max_length=128),
        ),
        migrations.AlterField(
            model_name='entitylocationrelationship',
            name='type',
            field=models.CharField(choices=[('ADMINISTRATIVE_AREA_LEVEL_1', 'ADMINISTRATIVE_AREA_LEVEL_1'), ('ADMINISTRATIVE_AREA_LEVEL_2', 'ADMINISTRATIVE_AREA_LEVEL_2'), ('COUNTRY', 'COUNTRY'), ('LOCALITY', 'LOCALITY'), ('POSTAL_CODE', 'POSTAL_CODE'), ('SUBLOCALITY', 'SUBLOCALITY')], max_length=128),
        ),
    ]
