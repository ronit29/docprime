# Generated by Django 2.0.5 on 2019-08-23 06:11

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0055_merge_20190711_1547'),
        ('diagnostic', '0220_auto_20190806_1635'),
    ]

    operations = [
        migrations.CreateModel(
            name='IPDMedicinePageLead',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=500)),
                ('phone_number', models.BigIntegerField()),
                ('city', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='common.MatrixMappedCity')),
            ],
            options={
                'db_table': 'ipd_medicine_lead',
            },
        ),
    ]
