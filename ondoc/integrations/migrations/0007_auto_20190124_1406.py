# Generated by Django 2.0.5 on 2019-01-24 08:36

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('integrations', '0006_auto_20190124_1155'),
    ]

    operations = [
        migrations.AddField(
            model_name='integratormapping',
            name='is_active',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='integratormapping',
            name='test',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='diagnostic.LabTest'),
        ),
    ]