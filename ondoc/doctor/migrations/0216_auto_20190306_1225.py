# Generated by Django 2.0.5 on 2019-03-06 06:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0215_merge_20190306_1225'),
    ]

    operations = [
        migrations.AlterField(
            model_name='hospital',
            name='about',
            field=models.TextField(blank=True, default=''),
        ),
    ]