# Generated by Django 2.0.5 on 2018-12-15 12:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('location', '0049_auto_20181215_1641'),
    ]

    operations = [
        migrations.AddField(
            model_name='entityaddress',
            name='full_name',
            field=models.TextField(blank=True, max_length=2000, null=True),
        ),
    ]
