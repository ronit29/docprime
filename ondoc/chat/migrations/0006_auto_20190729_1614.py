# Generated by Django 2.0.5 on 2019-07-29 10:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0005_chatconsultation'),
    ]

    operations = [
        migrations.AlterField(
            model_name='chatconsultation',
            name='id',
            field=models.BigAutoField(primary_key=True, serialize=False),
        ),
    ]