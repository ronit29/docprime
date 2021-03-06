# Generated by Django 2.0.5 on 2019-07-01 14:03

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('common', '0053_merge_20190626_1132'),
    ]

    operations = [
        migrations.CreateModel(
            name='Fraud',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('object_id', models.PositiveIntegerField()),
                ('reason', models.TextField(max_length=300)),
                ('content_type', models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to='contenttypes.ContentType')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'fraud',
            },
        ),
        migrations.AlterUniqueTogether(
            name='fraud',
            unique_together={('content_type', 'object_id')},
        ),
    ]
