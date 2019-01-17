# Generated by Django 2.0.5 on 2019-01-14 06:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0005_paymentoptions'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserConfig',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('image', models.ImageField(upload_to='config/images', verbose_name='Config image')),
                ('text', models.CharField(blank=True, max_length=1000, null=True)),
                ('rtl', models.BooleanField()),
            ],
            options={
                'db_table': 'user_config',
            },
        ),
    ]