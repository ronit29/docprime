# Generated by Django 2.0.5 on 2019-02-27 05:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0022_feature'),
    ]

    operations = [
        migrations.CreateModel(
            name='Service',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('icon', models.ImageField(upload_to='service/images', verbose_name='Service image')),
                ('name', models.CharField(max_length=100)),
            ],
            options={
                'db_table': 'service',
            },
        ),
    ]