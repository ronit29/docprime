# Generated by Django 2.0.5 on 2018-09-04 09:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0101_auto_20180904_1440'),
    ]

    operations = [
        migrations.AddField(
            model_name='doctor',
            name='qc_approved_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='hospital',
            name='live_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='hospital',
            name='qc_approved_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='hospitalnetwork',
            name='qc_approved_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
