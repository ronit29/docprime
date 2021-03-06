# Generated by Django 2.0.5 on 2018-10-30 09:50

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0149_auto_20181030_0817'),
    ]

    operations = [
        migrations.CreateModel(
            name='CancellationReason',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=200)),
            ],
            options={
                'db_table': 'cancellation_reason',
            },
        ),
        migrations.AddField(
            model_name='opdappointment',
            name='cancellation_comments',
            field=models.CharField(blank=True, max_length=5000, null=True),
        ),
        migrations.AlterUniqueTogether(
            name='cancellationreason',
            unique_together={('name',)},
        ),
        migrations.AddField(
            model_name='opdappointment',
            name='cancellation_reason',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='doctor.CancellationReason'),
        ),
    ]
