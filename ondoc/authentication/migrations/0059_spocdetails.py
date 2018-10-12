# Generated by Django 2.0.5 on 2018-10-10 07:00

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('authentication', '0058_auto_20180829_1443'),
    ]

    operations = [
        migrations.CreateModel(
            name='SPOCDetails',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=200)),
                ('std_code', models.IntegerField()),
                ('number', models.BigIntegerField()),
                ('email', models.EmailField(blank=True, max_length=100)),
                ('details', models.CharField(blank=True, max_length=200)),
                ('contact_type', models.PositiveSmallIntegerField(choices=[(1, 'Other'), (2, 'Single Point of Contact'), (3, 'Manager'), (4, 'Owner')])),
                ('object_id', models.PositiveIntegerField()),
                ('content_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.ContentType')),
            ],
            options={
                'db_table': 'spoc_details',
            },
        ),
    ]