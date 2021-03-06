# Generated by Django 2.0.5 on 2019-11-14 09:47

from django.conf import settings
import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('plus', '0040_auto_20191108_1539'),
    ]

    operations = [
        migrations.CreateModel(
            name='TempPlusUser',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('raw_plus_member', django.contrib.postgres.fields.jsonb.JSONField(default=list)),
                ('deleted', models.BooleanField(default=0)),
                ('plan', models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, related_name='temp_plus_plan', to='plus.PlusPlans')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, related_name='temp_plus_user', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'temp_plus_user',
            },
        ),
    ]
