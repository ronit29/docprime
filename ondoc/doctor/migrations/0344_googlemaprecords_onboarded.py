# Generated by Django 2.0.5 on 2020-02-04 12:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0343_auto_20200204_1412'),
    ]

    operations = [
        migrations.AddField(
            model_name='googlemaprecords',
            name='onboarded',
            field=models.SmallIntegerField(choices=[(2, 'Yes'), (3, 'No'), (4, 'Maybe'), (1, 'Null')], default=1),
        ),
    ]
