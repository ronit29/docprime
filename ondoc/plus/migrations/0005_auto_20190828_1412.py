# Generated by Django 2.0.5 on 2019-08-28 08:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('plus', '0004_remove_plusmembers_plus_user'),
    ]

    operations = [
        migrations.AlterField(
            model_name='plususer',
            name='id',
            field=models.BigAutoField(primary_key=True, serialize=False),
        ),
    ]