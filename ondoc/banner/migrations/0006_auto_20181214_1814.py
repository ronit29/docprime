# Generated by Django 2.0.5 on 2018-12-14 12:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('banner', '0005_auto_20181214_1647'),
    ]

    operations = [
        migrations.AlterField(
            model_name='banner',
            name='slider_locate',
            field=models.SmallIntegerField(choices=[(1, 'home_page'), (2, 'doctor_search_page'), (3, 'lab_search_page')]),
        ),
    ]
