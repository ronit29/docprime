# Generated by Django 2.0.5 on 2018-09-06 11:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0002_chatprescription'),
    ]

    operations = [
        migrations.AlterField(
            model_name='chatprescription',
            name='file',
            field=models.FileField(upload_to='chat/prescription'),
        ),
        migrations.AlterField(
            model_name='chatprescription',
            name='name',
            field=models.CharField(max_length=16, unique=True),
        ),
    ]
