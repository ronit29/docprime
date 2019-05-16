# Generated by Django 2.0.5 on 2019-04-30 10:41

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0195_merge_20190419_1241'),
        ('location', '0085_merge_20190320_1344'),
    ]

    operations = [
        migrations.CreateModel(
            name='CompareLabPackagesSeoUrls',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('lab', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='compare_lab', to='diagnostic.Lab')),
                ('package', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='compare_package', to='diagnostic.LabTest')),
            ],
            options={
                'db_table': 'compare_lab_packages_seo_urls',
            },
        ),
        migrations.CreateModel(
            name='CompareSEOUrls',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('url', models.CharField(db_index=True, max_length=2000, null=True, unique=True)),
            ],
            options={
                'db_table': 'compare_seo_urls',
            },
        ),
        migrations.AddField(
            model_name='comparelabpackagesseourls',
            name='url',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='compare_url', to='location.CompareSEOUrls'),
        ),
    ]
