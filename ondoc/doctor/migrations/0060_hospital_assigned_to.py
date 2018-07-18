# Generated by Django 2.0.5 on 2018-07-03 07:26

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('doctor', '0059_auto_20180702_1849'),
    ]

    operations = [
        migrations.AddField(
            model_name='hospital',
            name='assigned_to',
            field=models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_hospital', to=settings.AUTH_USER_MODEL),
        ),
    ]