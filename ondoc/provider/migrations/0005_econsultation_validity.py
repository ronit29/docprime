# Generated by Django 2.0.5 on 2019-08-07 11:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('provider', '0004_remove_econsultation_validity'),
    ]

    operations = [
        migrations.AddField(
            model_name='econsultation',
            name='validity',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
