# Generated by Django 2.0.2 on 2018-06-25 03:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='careers',
            name='profile_type',
            field=models.PositiveSmallIntegerField(choices=[('', 'Select Function'), (1, 'Product'), (2, 'Technology'), (3, 'Sales'), (4, 'Content'), (5, 'Marketing'), (6, 'QC'), (7, 'Support'), (8, 'Doctors')]),
        ),
    ]