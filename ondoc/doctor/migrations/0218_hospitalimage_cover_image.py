# Generated by Django 2.0.5 on 2019-03-10 16:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0217_auto_20190306_1243'),
    ]

    operations = [
        migrations.AddField(
            model_name='hospitalimage',
            name='cover_image',
            field=models.BooleanField(default=False, verbose_name="Can be used as Hospital's cover image?"),
        ),
    ]