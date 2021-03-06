# Generated by Django 2.0.5 on 2018-10-24 09:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('location', '0032_entityurls_specialization_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='CityInventory',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('city', models.TextField()),
            ],
            options={
                'db_table': 'seo_cities',
            },
        ),
    ]
