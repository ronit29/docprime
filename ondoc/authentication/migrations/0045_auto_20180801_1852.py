# Generated by Django 2.0.7 on 2018-08-01 13:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0044_auto_20180719_1827'),
    ]

    operations = [
        migrations.AddField(
            model_name='notificationendpoint',
            name='app_name',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='notificationendpoint',
            name='app_version',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='notificationendpoint',
            name='platform',
            field=models.TextField(blank=True, null=True),
        ),
    ]