# Generated by Django 2.0.5 on 2019-10-15 07:24

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('plus', '0035_auto_20191015_1225'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='plusplans',
            unique_together={('is_selected', 'is_gold')},
        ),
    ]
