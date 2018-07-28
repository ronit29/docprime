# Generated by Django 2.0.5 on 2018-07-27 11:51

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0066_auto_20180726_1629'),
    ]

    operations = [
        migrations.AlterField(
            model_name='labdocument',
            name='lab',
            field=models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='lab_documents', to='diagnostic.Lab'),
        ),
    ]
