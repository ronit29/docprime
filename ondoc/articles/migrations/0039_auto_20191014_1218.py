# Generated by Django 2.0.5 on 2019-10-14 06:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('articles', '0038_auto_20190911_1242'),
    ]

    operations = [
        migrations.AlterField(
            model_name='article',
            name='pharmeasy_product_id',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='article',
            name='pharmeasy_url',
            field=models.TextField(blank=True, null=True),
        ),
    ]
