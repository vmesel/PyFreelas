# Generated by Django 3.1.2 on 2021-02-23 21:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0056_auto_20210215_1557"),
    ]

    operations = [
        migrations.AddField(
            model_name="job",
            name="unique_slug",
            field=models.CharField(
                blank=True, max_length=1000, null=True, verbose_name="Slug Unica"
            ),
        ),
    ]
