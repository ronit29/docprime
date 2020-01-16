# Generated by Django 2.0.5 on 2020-01-16 06:51

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('plus', '0054_auto_20191205_1247'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='corporate',
            name='corporate_group',
        ),
        migrations.AlterField(
            model_name='plusplans',
            name='corporate_group',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='corporate_plan', to='corporate_booking.CorporateGroup'),
        ),
        migrations.DeleteModel(
            name='Corporate',
        ),
        migrations.DeleteModel(
            name='CorporateGroup',
        ),
    ]
