# Generated by Django 2.0.5 on 2018-06-18 07:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0048_auto_20180615_1906'),
    ]

    operations = [
        migrations.AlterField(
            model_name='doctorhospital',
            name='discounted_price',
            field=models.FloatField(default=0),
        ),
        migrations.AlterField(
            model_name='doctorhospital',
            name='fees',
            field=models.FloatField(),
        ),
        migrations.AlterField(
            model_name='opdappointment',
            name='discounted_price',
            field=models.FloatField(default=0),
        ),
        migrations.AlterField(
            model_name='opdappointment',
            name='effective_price',
            field=models.FloatField(default=0),
        ),
        migrations.AlterField(
            model_name='opdappointment',
            name='fees',
            field=models.FloatField(),
        ),
        migrations.AlterField(
            model_name='opdappointment',
            name='mrp',
            field=models.FloatField(default=0),
        ),
    ]