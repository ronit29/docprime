# Generated by Django 2.0.5 on 2018-10-09 06:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('location', '0026_auto_20181008_1527'),
    ]

    operations = [
        migrations.AddField(
            model_name='entityaddress',
            name='alternative_value',
            field=models.TextField(default=''),
        ),
    ]
