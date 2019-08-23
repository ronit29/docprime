# Generated by Django 2.0.5 on 2019-08-20 03:43

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0297_merge_20190819_1555'),
    ]

    operations = [
        migrations.CreateModel(
            name='HospitalNetworkImage',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('width', models.PositiveSmallIntegerField(blank=True, editable=False, null=True)),
                ('height', models.PositiveSmallIntegerField(blank=True, editable=False, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.ImageField(height_field='height', upload_to='hospital_network/images', width_field='width')),
                ('cropped_image', models.ImageField(blank=True, height_field='height', null=True, upload_to='hospital_network/images', width_field='width')),
                ('cover_image', models.BooleanField(default=False, verbose_name="Can be used as Hospital's cover image?")),
                ('network', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.HospitalNetwork')),
            ],
            options={
                'db_table': 'hospital_network_image',
            },
        ),
    ]
