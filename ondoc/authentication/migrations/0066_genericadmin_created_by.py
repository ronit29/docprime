# Generated by Django 2.0.5 on 2018-11-05 10:02

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0065_auto_20181105_1508'),
    ]

    operations = [
        migrations.AddField(
            model_name='genericadmin',
            name='created_by',
            field=models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL),
        ),
    ]
