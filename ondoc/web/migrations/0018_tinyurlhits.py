# Generated by Django 2.0.5 on 2018-09-25 13:41

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0017_onlinelead_utm_params'),
    ]

    operations = [
        migrations.CreateModel(
            name='TinyUrlHits',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('ip_address', models.CharField(blank=True, max_length=500, null=True)),
                ('tiny_url', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='web.TinyUrl')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
