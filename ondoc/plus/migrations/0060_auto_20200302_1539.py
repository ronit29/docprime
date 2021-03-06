# Generated by Django 2.0.5 on 2020-03-02 10:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('plus', '0059_delete_corporategroup'),
    ]

    operations = [
        migrations.AddField(
            model_name='plusplans',
            name='chat_plans',
            field=models.PositiveIntegerField(blank=True, choices=[(1, 'Normal Chat Plan'), (2, 'Premium Chat Plan')], null=True),
        ),
        migrations.AddField(
            model_name='plusplans',
            name='is_chat_included',
            field=models.NullBooleanField(),
        ),
    ]
