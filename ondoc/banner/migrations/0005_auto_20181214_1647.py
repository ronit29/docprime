# Generated by Django 2.0.5 on 2018-12-14 11:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('banner', '0004_auto_20181214_1544'),
    ]

    operations = [
        migrations.AlterField(
            model_name='banner',
            name='slider_action',
            field=models.SmallIntegerField(choices=[(1, 'Test'), (2, 'Procedure'), (4, 'Procedure Category'), (3, 'Specialization'), (5, 'Condition')]),
        ),
    ]