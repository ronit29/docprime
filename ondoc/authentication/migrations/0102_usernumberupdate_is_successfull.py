# Generated by Django 2.0.5 on 2019-07-09 08:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0101_usernumberupdate'),
    ]

    operations = [
        migrations.AddField(
            model_name='usernumberupdate',
            name='is_successfull',
            field=models.BooleanField(default=False),
        ),
    ]
