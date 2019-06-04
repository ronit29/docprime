# Generated by Django 2.0.5 on 2019-02-25 08:28

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('banner', '0023_auto_20190222_1757'),
    ]

    operations = [
        migrations.CreateModel(
            name='SliderLocation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(default='Home_Page', max_length=1000, null=True)),
            ],
            options={
                'db_table': 'slider_location',
            },
        ),
        migrations.AlterField(
            model_name='banner',
            name='slider_locate',
            field=models.SmallIntegerField(blank=True, choices=[(1, 'home_page'), (2, 'doctor_search_page'), (3, 'lab_search_page'), (5, 'procedure_search_page'), (4, 'package_search_page'), (6, 'offers_page')], default=1, null=True),
        ),
        migrations.AddField(
            model_name='banner',
            name='location',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='banner.SliderLocation'),
        ),
    ]