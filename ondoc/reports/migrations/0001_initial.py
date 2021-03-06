# Generated by Django 2.0.5 on 2018-08-07 10:16

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Report',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('report_name', models.CharField(max_length=100)),
                ('description', models.CharField(max_length=100)),
                ('sql', models.TextField()),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
