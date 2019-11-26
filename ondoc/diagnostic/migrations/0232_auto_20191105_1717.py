# Generated by Django 2.0.5 on 2019-11-05 11:47

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0072_certifications'),
        ('diagnostic', '0231_auto_20191018_1716'),
    ]

    operations = [
        migrations.AddField(
            model_name='labcertification',
            name='certification',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='lab_certifications', to='common.Certifications'),
        ),
        migrations.AddField(
            model_name='labnetworkcertification',
            name='certification',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='lab_network_certifications', to='common.Certifications'),
        ),
    ]
