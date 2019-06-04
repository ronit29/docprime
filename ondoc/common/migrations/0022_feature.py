# Generated by Django 2.0.5 on 2019-02-26 12:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0021_merge_20190214_1411'),
    ]

    operations = [
        migrations.CreateModel(
            name='Feature',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('icon', models.ImageField(upload_to='feature/images', verbose_name='Feature image')),
                ('name', models.CharField(max_length=100)),
            ],
            options={
                'db_table': 'feature',
            },
        ),
    ]