# Generated by Django 2.0.5 on 2018-08-08 10:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0092_merge_20180807_2014'),
    ]

    operations = [
        migrations.AddField(
            model_name='doctor',
            name='signature',
            field=models.ImageField(blank=True, null=True, upload_to='doctor/images', verbose_name='Doctor Signature'),
        ),
    ]
