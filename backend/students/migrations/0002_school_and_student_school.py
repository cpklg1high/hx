from django.db import migrations, models
import django.db.models.deletion

def seed_schools(apps, schema_editor):
    School = apps.get_model('students', 'School')
    data = [
        ('复旦附中青浦分校', 'fudanfuzhongqingpufenxiao'),
        ('青浦高级中学',   'qingpugaojizhongxue'),
        ('朱家角中学',     'zhujiajiaozhongxue'),
        ('青浦第一中学',   'qingpudiyizhongxue'),
        ('青浦东湖中学',   'qingpudonghuzhongxue'),
        ('青浦二中',       'qingpuerzhong'),
        ('实验中学（东）', 'shiyanzhongxuedong'),
        ('东方中学',       'dongfangzhongxue'),
        ('尚美中学',       'shangmeizhongxue'),
    ]
    for name, py in data:
        School.objects.get_or_create(name=name, defaults={'pinyin': py, 'is_active': True})

def unseed_schools(apps, schema_editor):
    School = apps.get_model('students', 'School')
    names = [
        '复旦附中青浦分校','青浦高级中学','朱家角中学','青浦第一中学',
        '青浦东湖中学','青浦二中','实验中学（东）','东方中学','尚美中学'
    ]
    School.objects.filter(name__in=names).delete()

def fill_student_school(apps, schema_editor):
    Student = apps.get_model('students', 'Student')
    School = apps.get_model('students', 'School')
    default_school = School.objects.order_by('pinyin', 'id').first()
    if default_school:
        Student.objects.filter(school__isnull=True).update(school=default_school)

class Migration(migrations.Migration):

    dependencies = [
        ('students', '0001_initial'),  # 如果你的上一条不是 0001，请改成你实际上一条
    ]

    operations = [
        # 1) 创建 School 表
        migrations.CreateModel(
            name='School',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('pinyin', models.CharField(db_index=True, max_length=120)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'edu_school',
                'ordering': ['pinyin', 'name'],
            },
        ),
        # 2) 给 Student 加外键（先允许为空，避免历史数据报错）
        migrations.AddField(
            model_name='student',
            name='school',
            field=models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.PROTECT, related_name='students', to='students.school'),
        ),
        # 3) 预置 9 所学校
        migrations.RunPython(seed_schools, reverse_code=unseed_schools),
        # 4) 回填老数据（把已有学生的 school 置为按拼音排序第一所）
        migrations.RunPython(fill_student_school, reverse_code=migrations.RunPython.noop),
        # 5) 收紧为必填（不允许为空）
        migrations.AlterField(
            model_name='student',
            name='school',
            field=models.ForeignKey(null=False, on_delete=django.db.models.deletion.PROTECT, related_name='students', to='students.school'),
        ),
    ]
