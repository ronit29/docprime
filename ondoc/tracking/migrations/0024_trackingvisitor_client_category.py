# Generated by Django 2.0.5 on 2019-03-18 08:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracking', '0023_migratetracker'),
    ]

    operations = [
        migrations.AddField(
            model_name='trackingvisitor',
            name='client_category',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
