# Generated by Django 2.0.5 on 2018-10-22 12:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('insurance', '0024_auto_20181022_1640'),
    ]

    operations = [
        migrations.AlterField(
            model_name='insuredmembers',
            name='dob',
            field=models.DateField(blank=True, null=True),
        ),
    ]
