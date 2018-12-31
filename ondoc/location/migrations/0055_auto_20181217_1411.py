# Generated by Django 2.0.5 on 2018-12-17 08:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('location', '0054_remove_entitylocationrelationship_valid'),
    ]

    operations = [
        migrations.AlterField(
            model_name='entitylocationrelationship',
            name='type',
            field=models.CharField(blank=True, choices=[('ADMINISTRATIVE_AREA_LEVEL_1', 'ADMINISTRATIVE_AREA_LEVEL_1'), ('ADMINISTRATIVE_AREA_LEVEL_2', 'ADMINISTRATIVE_AREA_LEVEL_2'), ('COUNTRY', 'COUNTRY'), ('LOCALITY', 'LOCALITY'), ('SUBLOCALITY', 'SUBLOCALITY')], max_length=128, null=True),
        ),
    ]