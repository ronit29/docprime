# Generated by Django 2.0.5 on 2019-03-20 11:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0171_merge_20190319_1219'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lab',
            name='search_key',
            field=models.CharField(blank=True, max_length=4000, null=True),
        ),
        migrations.AlterField(
            model_name='labtest',
            name='search_key',
            field=models.CharField(blank=True, max_length=4000, null=True),
        ),
        migrations.AlterField(
            model_name='labtestcategory',
            name='search_key',
            field=models.CharField(blank=True, max_length=4000, null=True),
        ),
    ]
