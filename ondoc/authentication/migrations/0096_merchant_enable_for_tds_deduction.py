# Generated by Django 2.0.5 on 2019-06-18 07:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0095_auto_20190517_1638'),
    ]

    operations = [
        migrations.AddField(
            model_name='merchant',
            name='enable_for_tds_deduction',
            field=models.BooleanField(default=False),
        ),
    ]
