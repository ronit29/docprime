# Generated by Django 2.0.5 on 2019-11-26 06:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notification', '0066_auto_20191126_1206'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ipdintimateemailnotification',
            name='gender',
            field=models.PositiveIntegerField(blank=True, choices=[('m', 'male'), ('f', 'female')], null=True),
        ),
    ]