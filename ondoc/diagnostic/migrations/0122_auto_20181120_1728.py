# Generated by Django 2.0.5 on 2018-11-20 11:58

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0121_auto_20181120_1654'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='labtest',
            name='faq',
        ),
        migrations.AddField(
            model_name='questionanswer',
            name='lab_test',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='faq', to='diagnostic.LabTest'),
        ),
    ]
