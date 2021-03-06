# Generated by Django 2.0.5 on 2018-11-06 11:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0002_auto_20180903_1508'),
    ]

    operations = [
        migrations.CreateModel(
            name='MatrixCityMapping',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('city_id', models.PositiveIntegerField()),
                ('name', models.CharField(db_index=True, max_length=48)),
            ],
            options={
                'db_table': 'matrix_city_mapping',
            },
        ),
    ]
