# Generated by Django 2.0.5 on 2018-10-17 08:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0135_auto_20181017_0033'),
    ]

    operations = [
        migrations.AlterField(
            model_name='hospital',
            name='state',
            field=models.CharField(blank=True, max_length=100),
        ),
    ]