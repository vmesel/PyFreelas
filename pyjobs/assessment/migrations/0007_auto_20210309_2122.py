# Generated by Django 3.1.7 on 2021-03-09 21:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("assessment", "0006_auto_20210309_2122"),
    ]

    operations = [
        migrations.AlterField(
            model_name="assessmentcategory",
            name="description",
            field=models.TextField(max_length=5000),
        ),
    ]