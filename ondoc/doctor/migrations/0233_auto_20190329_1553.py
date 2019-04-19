# Generated by Django 2.0.5 on 2019-03-29 10:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0232_merge_20190329_1136'),
    ]

    operations = [
        migrations.AddField(
            model_name='hospitalnetwork',
            name='physical_agreement_signed',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='hospitalnetwork',
            name='physical_agreement_signed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
