# Generated by Django 2.0.5 on 2018-12-26 09:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('location', '0063_defaultrating'),
    ]

    operations = [
        migrations.AddField(
            model_name='defaultrating',
            name='reviews',
            field=models.PositiveIntegerField(null=True),
        ),
    ]