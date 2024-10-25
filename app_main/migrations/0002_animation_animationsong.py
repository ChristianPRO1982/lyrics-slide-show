# Generated by Django 5.1.2 on 2024-10-25 14:06

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app_main', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Animation',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255, unique=True)),
                ('description', models.TextField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='AnimationSong',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('order', models.IntegerField()),
                ('animation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='animation_songs', to='app_main.animation')),
                ('song', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app_main.song')),
            ],
            options={
                'ordering': ['order'],
                'unique_together': {('animation', 'order')},
            },
        ),
    ]
