# Generated by Django 2.0.5 on 2019-02-27 06:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0203_auto_20190225_1453'),
    ]

    operations = [
        migrations.AlterField(
            model_name='providersignuplead',
            name='is_docprime',
            field=models.NullBooleanField(),
        ),
    ]