# Generated by Django 2.0.5 on 2019-10-07 06:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0114_auto_20190919_1102'),
    ]

    operations = [
        migrations.AddField(
            model_name='otpverifications',
            name='req_count',
            field=models.PositiveSmallIntegerField(blank=True, default=1, max_length=1, null=True),
        ),
    ]
