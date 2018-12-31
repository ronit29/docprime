# Generated by Django 2.0.5 on 2018-12-26 09:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('location', '0062_auto_20181220_1042'),
    ]

    operations = [
        migrations.CreateModel(
            name='DefaultRating',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('ratings', models.PositiveIntegerField(null=True)),
                ('url', models.TextField()),
            ],
            options={
                'db_table': 'default_rating',
            },
        ),
    ]