# Generated by Django 2.0.5 on 2019-03-06 06:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0213_hospital_about'),
    ]

    operations = [
        migrations.AlterField(
            model_name='hospitalhelpline',
            name='std_code',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
    ]
