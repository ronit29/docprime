# Generated by Django 2.0.5 on 2018-11-02 19:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0063_merge_20181025_1818'),
    ]

    operations = [
        migrations.AddField(
            model_name='spocdetails',
            name='source',
            field=models.CharField(blank=True, max_length=2000),
        ),
    ]
