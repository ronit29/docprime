# Generated by Django 2.0.5 on 2019-03-05 08:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracking', '0022_auto_20190208_1512'),
    ]

    operations = [
        migrations.CreateModel(
            name='MigrateTracker',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('start_time', models.DateTimeField(null=True)),
            ],
            options={
                'db_table': 'migrate_tracker',
            },
        ),
    ]