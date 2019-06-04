# Generated by Django 2.0.5 on 2019-05-21 14:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('insurance', '0112_merge_20190517_1958'),
    ]

    operations = [
        migrations.CreateModel(
            name='ThirdPartyAdministrator',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=500, unique=True)),
            ],
            options={
                'db_table': 'third_party_administrator',
            },
        ),
    ]