# Generated by Django 2.0.5 on 2019-03-07 09:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('procedure', '0024_auto_20190301_1344'),
    ]

    operations = [
        migrations.AddField(
            model_name='ipdprocedure',
            name='deleted',
            field=models.DateTimeField(editable=False, null=True),
        ),
    ]