# Generated by Django 2.0.5 on 2019-04-18 10:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0241_merge_20190417_1219'),
    ]

    operations = [
        migrations.AddField(
            model_name='partnersappinvoice',
            name='encoded_url',
            field=models.URLField(blank=True, max_length=300, null=True),
        ),
    ]
