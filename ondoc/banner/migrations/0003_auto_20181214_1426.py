# Generated by Django 2.0.5 on 2018-12-14 08:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('banner', '0002_auto_20181214_1220'),
    ]

    operations = [
        migrations.AlterField(
            model_name='banner',
            name='slider_action',
            field=models.SmallIntegerField(choices=[(1, 'Lab Test'), (2, 'Procedure'), (4, 'Procedure Category'), (3, 'Specialization')]),
        ),
        migrations.AlterField(
            model_name='banner',
            name='slider_location',
            field=models.SmallIntegerField(choices=[(1, 'Home Page'), (2, 'Doctor Search Page'), (3, 'Lab Search Page')]),
        ),
    ]
