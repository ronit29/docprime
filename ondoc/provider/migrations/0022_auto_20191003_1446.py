# Generated by Django 2.0.5 on 2019-10-03 09:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('provider', '0021_partnerlabsamplescollectorder_created_by'),
    ]

    operations = [
        migrations.AlterField(
            model_name='partnerlabsamplescollectorder',
            name='id',
            field=models.BigAutoField(primary_key=True, serialize=False),
        ),
    ]
