# Generated by Django 2.0.5 on 2018-10-10 09:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0060_auto_20181010_1433'),
    ]

    operations = [
        migrations.AlterField(
            model_name='spocdetails',
            name='email',
            field=models.EmailField(blank=True, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name='spocdetails',
            name='number',
            field=models.BigIntegerField(blank=True, null=True),
        ),
    ]
