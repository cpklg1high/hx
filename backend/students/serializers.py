from rest_framework import serializers
from django.db import transaction
from django.contrib.auth import get_user_model

from .models import (
    Student, Guardian, StudentGuardian, School,
    RELATION_CHOICES, GRADE_CHOICES, VISIT_CHANNEL, ReferralReward
)
from academics.models import Enrollment

User = get_user_model()

# --- 嵌套监护人输入 ---
class GuardianInlineIn(serializers.Serializer):
    relation_code = serializers.ChoiceField(choices=[c[0] for c in RELATION_CHOICES])
    guardian_name = serializers.CharField(max_length=50, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=20)
    is_primary = serializers.BooleanField()
    remark = serializers.CharField(max_length=200, required=False, allow_blank=True)

class StudentListOut(serializers.ModelSerializer):
    grade_label = serializers.SerializerMethodField()
    school_name = serializers.CharField(source='school.name')
    primary_contact = serializers.SerializerMethodField()
    other_contacts_count = serializers.SerializerMethodField()
    current_salesperson = serializers.SerializerMethodField()
    visit_channel = serializers.CharField()
    visit_channel_label = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = [
            'id', 'name', 'grade', 'grade_label', 'school_name',
            'primary_contact', 'other_contacts_count',
            'current_salesperson', 'academic_status', 'created_at',
            'visit_channel', 'visit_channel_label'
        ]

    def get_grade_label(self, obj):
        d = dict(GRADE_CHOICES); return d.get(obj.grade, '')

    def get_visit_channel_label(self, obj):
        from .models import VISIT_CHANNEL
        return dict(VISIT_CHANNEL).get(obj.visit_channel, '')

    def get_primary_contact(self, obj):
        link = obj.guardian_links.filter(is_primary=True).select_related('guardian').first()
        if not link: return None
        rel_map = dict(RELATION_CHOICES)
        return {'relation_label': rel_map.get(link.relation_code, ''),
                'phone': link.guardian.phone}

    def get_other_contacts_count(self, obj):
        cnt = obj.guardian_links.count()
        return max(0, cnt - 1)

    def get_current_salesperson(self, obj):
        if not obj.current_salesperson: return None
        return {'id': obj.current_salesperson_id, 'name': obj.current_salesperson.name or obj.current_salesperson.username}

class StudentIn(serializers.Serializer):
    name = serializers.CharField(max_length=50)
    grade_id = serializers.IntegerField()
    school_id = serializers.IntegerField()  # 必填：学校
    current_salesperson_id = serializers.IntegerField(required=False, allow_null=True)
    visit_channel = serializers.ChoiceField(choices=[c[0] for c in VISIT_CHANNEL])
    referral_student_id = serializers.IntegerField(required=False, allow_null=True)
    visit_channel_other_text = serializers.CharField(max_length=100, required=False, allow_blank=True)
    remark = serializers.CharField(max_length=500, required=False, allow_blank=True)

    guardians = GuardianInlineIn(many=True)

    def validate(self, attrs):
        # 年级合法
        if attrs.get('grade_id') not in dict(GRADE_CHOICES):
            raise serializers.ValidationError({'grade_id': '年级不在 K12 范围'})

        # 学校存在
        sid = attrs.get('school_id')
        if not School.objects.filter(id=sid, is_active=True).exists():
            raise serializers.ValidationError({'school_id': '请选择有效学校'})

        # 渠道依赖校验
        vc = attrs.get('visit_channel')
        ref_id = attrs.get('referral_student_id')
        other_text = attrs.get('visit_channel_other_text', '')
        if vc == 'referral':
            if not ref_id:
                raise serializers.ValidationError({'referral_student_id': '转介绍必须选择推荐学员'})
            if not Enrollment.is_student_studying(ref_id):  # 只看派生在读
                raise serializers.ValidationError({'referral_student_id': '仅支持在读学员作为推荐人'})
        elif vc == 'other':
            if not other_text:
                raise serializers.ValidationError({'visit_channel_other_text': '其他方式说明必填'})
        else:
            if ref_id or other_text:
                raise serializers.ValidationError('直访无需填写转介绍/其他说明')

        # 监护人：至少一位，且唯一主联系人
        gs = attrs.get('guardians') or []
        if not gs:
            raise serializers.ValidationError({'guardians': '至少添加一位联系人'})
        primary = [g for g in gs if g.get('is_primary')]
        if len(primary) != 1:
            raise serializers.ValidationError({'guardians': '必须且仅有一位主联系人'})

        return attrs

    @transaction.atomic
    def create(self, validated):
        req = self.context.get('request')
        user = getattr(req, 'user', None) if req else None

        stu = Student.objects.create(
            name=validated['name'],
            grade=validated['grade_id'],
            school_id=validated['school_id'],
            current_salesperson_id=validated.get('current_salesperson_id'),
            visit_channel=validated['visit_channel'],
            referral_student_id=validated.get('referral_student_id'),
            visit_channel_other_text=validated.get('visit_channel_other_text') or '',
            remark=validated.get('remark') or '',
            created_by=user if user and user.is_authenticated else None,
            updated_by=user if user and user.is_authenticated else None,
        )

        # 监护人
        links = []
        for g in validated['guardians']:
            guardian = Guardian.objects.create(
                name=g.get('guardian_name') or '',
                phone=g['phone'],
            )
            links.append(StudentGuardian(
                student=stu, guardian=guardian,
                relation_code=g['relation_code'],
                is_primary=g['is_primary'],
                remark=g.get('remark') or ''
            ))
        StudentGuardian.objects.bulk_create(links)

        # 转介绍奖励（pending）
        if stu.visit_channel == 'referral' and stu.referral_student_id:
            rr = ReferralReward.objects.create(
                referrer_student_id=stu.referral_student_id,
                new_student=stu,
                status='pending'
            )
            rr.set_rule_snapshot({'note': '系统初建，待运营审核'})
            rr.save()

        return stu
