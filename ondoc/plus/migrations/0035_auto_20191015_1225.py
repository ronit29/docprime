# Generated by Django 2.0.5 on 2019-10-15 06:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('plus', '0034_auto_20191014_1304'),
    ]

    operations = [
        migrations.AlterField(
            model_name='plusplans',
            name='tenure',
            field=models.PositiveIntegerField(default=1, help_text='Tenure is number of months of active subscription.'),
        ),
    ]