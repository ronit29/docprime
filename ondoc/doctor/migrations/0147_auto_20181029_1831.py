# Generated by Django 2.0.5 on 2018-10-29 13:01

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0146_merge_20181029_1544'),
    ]

    operations = [
        migrations.CreateModel(
            name='VisitReason',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.TextField()),
                ('is_primary', models.BooleanField(default=False)),
                ('practice_specialization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='doctor.PracticeSpecialization')),
            ],
            options={
                'db_table': 'visit_reason',
            },
        ),
        migrations.AlterUniqueTogether(
            name='visitreason',
            unique_together={('name', 'practice_specialization')},
        ),
    ]