# Generated by Django 2.0.5 on 2019-11-01 10:53

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0231_auto_20191101_1545'),
    ]

    operations = [
        migrations.AlterField(
            model_name='labtest',
            name='search_name',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='diagnostic.LabtestNameMaster'),
        ),
    ]