# Generated by Django 2.0.5 on 2019-08-28 06:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0222_auto_20190827_1809'),
    ]

    operations = [
        migrations.AddField(
            model_name='ipdmedicinepagelead',
            name='lead_source',
            field=models.CharField(max_length=1000, null=True),
        ),
        migrations.AddField(
            model_name='ipdmedicinepagelead',
            name='matrix_lead_id',
            field=models.IntegerField(null=True),
        ),
    ]