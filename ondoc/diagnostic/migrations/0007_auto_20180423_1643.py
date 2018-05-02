# Generated by Django 2.0.2 on 2018-04-23 11:13

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0006_auto_20180423_1600'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='activelabservice',
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name='activelabservice',
            name='lab',
        ),
        migrations.RemoveField(
            model_name='activelabservice',
            name='lab_service',
        ),
        migrations.AddField(
            model_name='labservice',
            name='lab',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='diagnostic.Lab'),
        ),
        migrations.AlterField(
            model_name='labdocument',
            name='lab',
            field=models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.CASCADE, to='diagnostic.Lab'),
        ),
        migrations.AlterField(
            model_name='labservice',
            name='name',
            field=models.CharField(choices=[('1', 'Pathology'), ('2', 'Radiology')], max_length=2),
        ),
        migrations.DeleteModel(
            name='ActiveLabService',
        ),
    ]
