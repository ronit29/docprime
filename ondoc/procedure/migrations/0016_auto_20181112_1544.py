# Generated by Django 2.0.5 on 2018-11-12 10:14

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('procedure', '0015_auto_20181112_1541'),
    ]

    operations = [
        migrations.RenameField(
            model_name='commonprocedurecategory',
            old_name='procedure',
            new_name='procedure_category',
        ),
    ]
