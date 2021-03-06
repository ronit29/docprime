# Generated by Django 2.0.5 on 2019-01-02 12:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('insurance', '0058_insurancethreshold_child_max_age'),
    ]

    operations = [
        migrations.CreateModel(
            name='StateGSTCode',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('gst_code', models.CharField(max_length=10)),
                ('state_name', models.CharField(max_length=100)),
                ('is_enabled', models.BooleanField(default=True)),
                ('is_live', models.BooleanField(default=True)),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
