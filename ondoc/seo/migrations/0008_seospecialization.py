# Generated by Django 2.0.5 on 2018-10-30 10:28

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0149_auto_20181030_0817'),
        ('seo', '0007_auto_20181011_2022'),
    ]

    operations = [
        migrations.CreateModel(
            name='SeoSpecialization',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('rank', models.PositiveIntegerField(default=0, null=True)),
                ('specialization', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='doctor.PracticeSpecialization')),
            ],
            options={
                'db_table': 'seo_specialization',
            },
        ),
    ]