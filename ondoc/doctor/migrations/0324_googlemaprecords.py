# Generated by Django 2.0.5 on 2019-11-19 09:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0323_merge_20191106_1315'),
    ]

    operations = [
        migrations.CreateModel(
            name='GoogleMapRecords',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('location', models.CharField(max_length=100)),
                ('text', models.CharField(max_length=500)),
                ('latitude', models.DecimalField(decimal_places=6, default=None, max_digits=9)),
                ('longitude', models.DecimalField(decimal_places=6, default=None, max_digits=9)),
                ('label', models.CharField(max_length=100, null=True)),
                ('image', models.URLField(max_length=500, null=True)),
            ],
            options={
                'db_table': 'google_map_records',
            },
        ),
    ]
