# Generated by Django 2.0.5 on 2019-04-16 09:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0032_merge_20190409_1318'),
    ]

    operations = [
        migrations.AlterField(
            model_name='appointmenthistory',
            name='source',
            field=models.CharField(blank=True, choices=[('c_app', 'Consumer App'), ('crm', 'CRM'), ('web', 'Consumer Web'), ('d_app', 'Doctor App'), ('d_web', 'Provider Web'), ('d_web_url', 'Doctor Web URL'), ('d_token_url', 'Doctor Token URL'), ('ivr', 'Auto IVR')], default='', max_length=10),
        ),
    ]
