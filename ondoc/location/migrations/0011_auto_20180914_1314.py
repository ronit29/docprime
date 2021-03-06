# Generated by Django 2.0.5 on 2018-09-14 07:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('location', '0010_remove_entityurls_valid_reference'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='entityaddress',
            name='centroid',
        ),
        migrations.AddField(
            model_name='entityaddress',
            name='latitude',
            field=models.DecimalField(decimal_places=8, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='entityaddress',
            name='longitude',
            field=models.DecimalField(decimal_places=8, max_digits=10, null=True),
        ),
        migrations.AlterField(
            model_name='entityaddress',
            name='type',
            field=models.CharField(choices=[('ADMINISTRATIVE_AREA_LEVEL_1', 'ADMINISTRATIVE_AREA_LEVEL_1'), ('ADMINISTRATIVE_AREA_LEVEL_2', 'ADMINISTRATIVE_AREA_LEVEL_1'), ('COUNTRY', 'COUNTRY'), ('LOCALITY', 'LOCALITY'), ('RAW_JSON', 'RAW_JSON'), ('SUBLOCALITY', 'SUBLOCALITY')], max_length=128),
        ),
        migrations.AlterField(
            model_name='entitylocationrelationship',
            name='type',
            field=models.CharField(choices=[('ADMINISTRATIVE_AREA_LEVEL_1', 'ADMINISTRATIVE_AREA_LEVEL_1'), ('ADMINISTRATIVE_AREA_LEVEL_2', 'ADMINISTRATIVE_AREA_LEVEL_1'), ('COUNTRY', 'COUNTRY'), ('LOCALITY', 'LOCALITY'), ('RAW_JSON', 'RAW_JSON'), ('SUBLOCALITY', 'SUBLOCALITY')], max_length=128),
        ),
    ]
