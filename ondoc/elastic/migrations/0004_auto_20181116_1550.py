# Generated by Django 2.0.5 on 2018-11-16 10:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('elastic', '0003_demoelastic_path'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='demoelastic',
            name='path',
        ),
        migrations.AddField(
            model_name='demoelastic',
            name='query',
            field=models.TextField(null=True),
        ),
    ]
