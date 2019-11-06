# Generated by Django 2.0.5 on 2019-09-27 11:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0318_merge_20190916_1822'),
    ]

    operations = [
        migrations.AddField(
            model_name='hospital',
            name='google_ratings_count',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='hospital',
            name='google_avg_rating',
            field=models.DecimalField(decimal_places=2, max_digits=5, null=True),
        ),
    ]