# Generated by Django 2.0.5 on 2019-07-10 10:24

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0276_auto_20190708_1550'),
    ]

    operations = [
        migrations.CreateModel(
            name='SimilarSpecializationGroup',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.SlugField(unique=True)),
            ],
            options={
                'db_table': 'similar_specialization_group',
            },
        ),
        migrations.CreateModel(
            name='SimilarSpecializationGroupMapping',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.SimilarSpecializationGroup')),
                ('specialization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.PracticeSpecialization')),
            ],
            options={
                'db_table': 'similar_specialization_group_mapping',
            },
        ),
        migrations.AddField(
            model_name='similarspecializationgroup',
            name='specializations',
            field=models.ManyToManyField(through='doctor.SimilarSpecializationGroupMapping', to='doctor.PracticeSpecialization'),
        ),
    ]
