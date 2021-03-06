# Generated by Django 2.0.5 on 2019-05-10 07:03

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('corporate_booking', '0005_auto_20190510_1152'),
    ]

    operations = [
        migrations.AlterField(
            model_name='corporates',
            name='matrix_city',
            field=models.ForeignKey(default='', on_delete=django.db.models.deletion.CASCADE, related_name='citymatrix', to='common.MatrixMappedCity', verbose_name='city'),
        ),
        migrations.AlterField(
            model_name='corporates',
            name='matrix_state',
            field=models.ForeignKey(default='', on_delete=django.db.models.deletion.CASCADE, related_name='statematrix', to='common.MatrixMappedState', verbose_name='state'),
        ),
    ]
