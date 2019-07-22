# Generated by Django 2.0.5 on 2019-07-09 07:48

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0100_merchanttdsdeduction'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserNumberUpdate',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('old_number', models.CharField(default=None, max_length=10, null=True)),
                ('new_number', models.CharField(default=None, max_length=10, null=True)),
                ('otp', models.IntegerField(blank=True, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, related_name='number_updates', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'user_number_updates',
            },
        ),
    ]