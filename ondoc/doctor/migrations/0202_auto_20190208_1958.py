# Generated by Django 2.0.5 on 2019-02-08 14:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0201_auto_20190207_1826'),
    ]

    operations = [
        migrations.AddField(
            model_name='hospital',
            name='matrix_lead_id',
            field=models.BigIntegerField(blank=True, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='hospitalnetwork',
            name='matrix_lead_id',
            field=models.BigIntegerField(blank=True, null=True, unique=True),
        ),
    ]