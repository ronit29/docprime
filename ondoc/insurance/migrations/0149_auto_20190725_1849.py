# Generated by Django 2.0.5 on 2019-07-25 13:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('insurance', '0148_userinsurance_onhold_reason'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userinsurance',
            name='onhold_reason',
            field=models.TextField(blank=True, max_length=200, null=True),
        ),
    ]
