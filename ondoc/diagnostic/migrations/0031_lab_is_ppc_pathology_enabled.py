# Generated by Django 2.0.5 on 2018-06-02 05:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0030_merge_20180528_1831'),
    ]

    operations = [
        migrations.AddField(
            model_name='lab',
            name='is_ppc_pathology_enabled',
            field=models.BooleanField(default=False, verbose_name='Enabled for Pre Policy Checkup'),
        ),
    ]
