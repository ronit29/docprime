# Generated by Django 2.0.5 on 2018-12-20 05:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('location', '0061_auto_20181219_2042'),
    ]

    operations = [
        migrations.AlterField(
            model_name='entityurls',
            name='url',
            field=models.CharField(db_index=True, max_length=2000, null=True),
        ),
    ]
