# Generated by Django 2.0.2 on 2018-04-16 10:40

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('doctor', '0010_auto_20180416_1536'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='college',
            name='created_by',
        ),
        migrations.RemoveField(
            model_name='qualification',
            name='created_by',
        ),
        migrations.RemoveField(
            model_name='specialization',
            name='created_by',
        ),
        migrations.AddField(
            model_name='hospitalnetwork',
            name='created_by',
            field=models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='hospitalnetwork',
            name='data_status',
            field=models.PositiveSmallIntegerField(choices=[(1, 'In Progress'), (2, 'Submitted For QC Check'), (3, 'QC approved')], default=1, editable=False),
        ),
    ]
