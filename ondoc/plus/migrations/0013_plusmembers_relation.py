# Generated by Django 2.0.5 on 2019-08-30 12:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('plus', '0012_auto_20190829_1851'),
    ]

    operations = [
        migrations.AddField(
            model_name='plusmembers',
            name='relation',
            field=models.CharField(choices=[('BROTHER', 'BROTHER'), ('DAUGHTER', 'DAUGHTER'), ('FATHER', 'FATHER'), ('MOTHER', 'MOTHER'), ('OTHERS', 'OTHERS'), ('SELF', 'SELF'), ('SISTER', 'SISTER'), ('SON', 'SON'), ('SPOUSE', 'SPOUSE'), ('SPOUSE_FATHER', 'SPOUSE_FATHER'), ('SPOUSE_MOTHER', 'SPOUSE_MOTHER')], default=None, max_length=50),
        ),
    ]
