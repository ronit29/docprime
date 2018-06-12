# Generated by Django 2.0.5 on 2018-06-12 05:48

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0029_auto_20180605_1113'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notificationendpoint',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='notification_endpoints', to=settings.AUTH_USER_MODEL),
        ),
    ]
