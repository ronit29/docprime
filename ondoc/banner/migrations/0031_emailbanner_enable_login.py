# Generated by Django 2.0.5 on 2019-05-14 08:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('banner', '0030_auto_20190513_0905'),
    ]

    operations = [
        migrations.AddField(
            model_name='emailbanner',
            name='enable_login',
            field=models.BooleanField(default=False),
        ),
    ]
