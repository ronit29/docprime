# Generated by Django 2.0.5 on 2019-03-14 07:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subscription_plan', '0007_auto_20190313_2301'),
    ]

    operations = [
        migrations.AddField(
            model_name='planfeature',
            name='name',
            field=models.CharField(default='', max_length=150),
        ),
    ]
