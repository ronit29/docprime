# Generated by Django 2.0.5 on 2018-10-24 09:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('location', '0031_entityurls_specialization'),
    ]

    operations = [
        migrations.AddField(
            model_name='entityurls',
            name='specialization_id',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
