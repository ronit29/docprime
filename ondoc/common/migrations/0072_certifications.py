# Generated by Django 2.0.5 on 2019-11-05 06:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0071_searchcriteria'),
    ]

    operations = [
        migrations.CreateModel(
            name='Certifications',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=200)),
            ],
            options={
                'db_table': 'certifications',
            },
        ),
    ]
