# Generated by Django 2.0.5 on 2019-04-19 11:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0245_merge_20190419_1314'),
    ]

    operations = [
        migrations.AlterField(
            model_name='partnersappinvoice',
            name='invoice_title',
            field=models.CharField(blank=True, max_length=300, null=True),
        ),
    ]