# Generated by Django 2.0.5 on 2018-09-26 12:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0003_auto_20180906_1638'),
    ]

    operations = [
        migrations.AlterField(
            model_name='chatprescription',
            name='name',
            field=models.CharField(max_length=100, unique=True),
        ),
    ]
