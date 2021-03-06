# Generated by Django 2.0.5 on 2018-12-17 17:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('location', '0058_entityaddress_geocoding'),
    ]

    operations = [
        migrations.RenameField(
            model_name='addressgeomapping',
            old_name='address',
            new_name='entity_address',
        ),
        migrations.AlterField(
            model_name='entityaddress',
            name='geocoding',
            field=models.ManyToManyField(related_name='entity_addresses', through='location.AddressGeoMapping', to='location.GeocodingResults'),
        ),
        migrations.AlterUniqueTogether(
            name='addressgeomapping',
            unique_together={('entity_address', 'geocoding_result')},
        ),
    ]
