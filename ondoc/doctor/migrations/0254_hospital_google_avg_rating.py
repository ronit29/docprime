# Generated by Django 2.0.5 on 2019-05-16 11:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0253_auto_20190509_1509'),
    ]

    operations = [
        migrations.AddField(
            model_name='hospital',
            name='google_avg_rating',
            field=models.DecimalField(decimal_places=2, editable=False, max_digits=5, null=True),
        ),
    ]
