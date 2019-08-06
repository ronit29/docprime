# Generated by Django 2.0.5 on 2019-08-06 11:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0284_merge_20190726_1626'),
    ]

    operations = [
        migrations.AlterField(
            model_name='doctor',
            name='disabled_after',
            field=models.PositiveIntegerField(blank=True, choices=[('', 'Select'), (1, 'Welcome Calling'), (2, 'Escalation'), (3, 'INSURANCE')], null=True),
        ),
        migrations.AlterField(
            model_name='hospital',
            name='disabled_after',
            field=models.PositiveIntegerField(blank=True, choices=[('', 'Select'), (1, 'Welcome Calling'), (2, 'Escalation'), (3, 'INSURANCE')], null=True),
        ),
    ]