# Generated by Django 2.0.5 on 2019-02-06 12:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0151_merge_20190204_0951'),
    ]

    operations = [
        migrations.AddField(
            model_name='labnetwork',
            name='is_mask_number_required',
            field=models.BooleanField(default=True),
        ),
    ]
