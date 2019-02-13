# Generated by Django 2.0.5 on 2019-02-13 11:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0015_appointmenthistory_source'),
    ]

    operations = [
        migrations.AlterField(
            model_name='appointmenthistory',
            name='source',
            field=models.CharField(blank=True, choices=[('others', 'Others'), ('crm', 'CRM'), ('web', 'Web'), ('app', 'App')], default='', max_length=10),
        ),
    ]
