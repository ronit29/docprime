# Generated by Django 2.0.5 on 2019-08-28 08:43

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('plus', '0005_auto_20190828_1412'),
    ]

    operations = [
        migrations.AddField(
            model_name='plusmembers',
            name='plus_user',
            field=models.ForeignKey(default=None, on_delete=django.db.models.deletion.DO_NOTHING, related_name='plus_members', to='plus.PlusUser'),
        ),
        migrations.AddField(
            model_name='plusplans',
            name='features',
            field=django.contrib.postgres.fields.jsonb.JSONField(default=dict),
        ),
    ]
