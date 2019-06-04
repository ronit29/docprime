# Generated by Django 2.0.5 on 2019-05-02 12:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('prescription', '0002_auto_20190501_1843'),
    ]

    operations = [
        migrations.AlterField(
            model_name='prescriptiondiagnoses',
            name='name',
            field=models.CharField(db_index=True, max_length=128),
        ),
        migrations.AlterField(
            model_name='prescriptionmedicine',
            name='name',
            field=models.CharField(db_index=True, max_length=128),
        ),
        migrations.AlterField(
            model_name='prescriptionspecialinstructions',
            name='name',
            field=models.CharField(db_index=True, max_length=128),
        ),
        migrations.AlterField(
            model_name='prescriptionsymptomscomplaints',
            name='name',
            field=models.CharField(db_index=True, max_length=128),
        ),
        migrations.AlterField(
            model_name='prescriptiontests',
            name='name',
            field=models.CharField(db_index=True, max_length=128),
        ),
    ]