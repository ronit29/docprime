# Generated by Django 2.0.5 on 2018-12-19 13:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('lead', '0005_searchlead'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserLead',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=50)),
                ('phone_number', models.CharField(max_length=15)),
                ('message', models.TextField(blank=True, null=True)),
                ('gender', models.PositiveSmallIntegerField(choices=[(1, 'male'), (2, 'female'), (3, 'other')])),
            ],
            options={
                'db_table': 'user_lead',
            },
        ),
    ]