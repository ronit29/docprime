# Generated by Django 2.0.5 on 2019-05-21 06:11

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0254_merge_20190510_1419'),
        ('procedure', '0047_ipdprocedurepracticespecialization'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='ipdprocedurepracticespecialization',
            unique_together={('ipd_procedure', 'practice_specialization')},
        ),
    ]