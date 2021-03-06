# Generated by Django 2.0.5 on 2018-12-17 16:53

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('location', '0055_auto_20181217_1411'),
    ]

    operations = [
        migrations.CreateModel(
            name='AddressGeoMapping',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('address', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='address_geos', to='location.EntityAddress')),
                ('geocoding_result', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='geo_addresses', to='location.GeocodingResults')),
            ],
            options={
                'db_table': 'address_geo_mapping',
            },
        ),
        migrations.AlterUniqueTogether(
            name='addressgeomapping',
            unique_together={('address', 'geocoding_result')},
        ),
    ]
