# Generated by Django 2.0.5 on 2018-06-25 09:58

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('diagnostic', '0047_auto_20180625_1024'),
    ]

    operations = [
        migrations.RunSQL(
            '''create or replace function labtest_agreed_price_calculate(mrp numeric, percent numeric)
                RETURNS numeric LANGUAGE plpgsql STABLE as $$
                DECLARE
                agreed_price numeric;
                BEGIN 
                agreed_price = ceil(mrp*percent/100);
                if agreed_price>mrp then 
                agreed_price=mrp;
                end if;
                return agreed_price;
                END;
                $$;'''
        ),
        migrations.RunSQL(
            '''create or replace function labtest_deal_price_calculate(mrp numeric, agreed_price numeric, percent numeric)
                RETURNS numeric LANGUAGE plpgsql STABLE as $$
                DECLARE
                deal_price numeric;
                BEGIN 
                deal_price = ceil(ceil(mrp*percent/100)/10)*10- 1;
                if deal_price>mrp then 
                deal_price=mrp;
                end if;
                if deal_price<agreed_price then 
                deal_price=agreed_price;
                end if;
                return deal_price;
                END;
                $$;'''
        ),

    ]