# Generated by Django 2.0.5 on 2019-02-11 10:24

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0018_auto_20190211_1503'),
        ('doctor', '0202_auto_20190208_1958'),
    ]

    operations = [
        migrations.AddField(
            model_name='hospital',
            name='matrix_city',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='hospitals_in_city', to='common.MatrixMappedCity', verbose_name='City'),
        ),
        migrations.AddField(
            model_name='hospital',
            name='matrix_state',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='hospitals_in_state', to='common.MatrixMappedState', verbose_name='State'),
        ),
    ]
