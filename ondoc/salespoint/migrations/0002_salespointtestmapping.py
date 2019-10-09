# Generated by Django 2.0.5 on 2019-04-04 07:24

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0181_auto_20190403_1544'),
        ('salespoint', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SalespointTestmapping',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True)),
                ('salespoint', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='salespoint.SalesPoint')),
                ('test', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='diagnostic.AvailableLabTest')),
            ],
            options={
                'db_table': 'salespoint_test_mapping',
            },
        ),
    ]
