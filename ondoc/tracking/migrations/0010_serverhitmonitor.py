# Generated by Django 2.0.5 on 2018-09-27 04:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracking', '0009_trackingvisit_data'),
    ]

    operations = [
        migrations.CreateModel(
            name='ServerHitMonitor',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('url', models.TextField(null=True)),
                ('refferar', models.CharField(default=None, max_length=255)),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
