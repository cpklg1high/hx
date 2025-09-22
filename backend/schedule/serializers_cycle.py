from rest_framework import serializers
from .models import Campus, Cycle, CycleRoster, CyclePublishLog, ClassGroup, Lesson ,CyclePreplanSlot, ClassGroup, Room, User

class CampusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campus
        fields = ['id','name','code','address','is_active']

class CycleSerializer(serializers.ModelSerializer):
    campus = CampusSerializer(read_only=True)
    campus_id = serializers.PrimaryKeyRelatedField(
        queryset=Campus.objects.all(), source='campus', write_only=True
    )
    class Meta:
        model = Cycle
        fields = [
            'id','name','term','term_type','year','campus','campus_id',
            'date_from','date_to','pattern','rest_weekday','status','remark',
            'created_by','created_at','updated_at'
        ]
        read_only_fields = ['created_by','created_at','updated_at','status']

class CycleRosterSerializer(serializers.ModelSerializer):
    class Meta:
        model = CycleRoster
        fields = ['id','cycle','class_group','student','type','track','note','created_by','created_at']
        read_only_fields = ['created_by','created_at']

class CyclePublishLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = CyclePublishLog
        fields = ['id','cycle','scope','mode','payload','diff_stats','published_by','published_at']
        read_only_fields = ['published_by','published_at']

class CycleMasterRosterItemSerializer(serializers.Serializer):
    roster_id = serializers.IntegerField()
    cycle_id = serializers.IntegerField()
    class_group_id = serializers.IntegerField()
    class_group_name = serializers.CharField(allow_blank=True, required=False)
    subject_id = serializers.IntegerField()
    subject_name = serializers.CharField()
    course_mode = serializers.CharField()
    grade = serializers.IntegerField()
    track = serializers.CharField(allow_null=True, required=False)
    type = serializers.CharField()
    student_id = serializers.IntegerField()
    student_name = serializers.CharField()
    teacher_id = serializers.IntegerField(allow_null=True, required=False)
    teacher_name = serializers.CharField(allow_null=True, required=False)

class CyclePreplanSlotSerializer(serializers.ModelSerializer):
    class_group_name = serializers.SerializerMethodField()
    subject_name = serializers.SerializerMethodField()
    teacher_name = serializers.SerializerMethodField()
    room_name = serializers.SerializerMethodField()

    class Meta:
        model = CyclePreplanSlot
        fields = [
            'id', 'cycle', 'class_group', 'weekday',
            'start_time', 'end_time',
            'teacher_override', 'room_override',
            'class_group_name', 'subject_name', 'teacher_name', 'room_name',
            'note', 'created_by', 'created_at'
        ]
        read_only_fields = ['created_by', 'created_at']

    def get_class_group_name(self, obj):
        return (obj.class_group.name or '') if obj.class_group_id else ''

    def get_subject_name(self, obj):
        try:
            return obj.class_group.subject.name
        except Exception:
            return ''

    def get_teacher_name(self, obj):
        t = obj.teacher_override or getattr(obj.class_group, 'teacher_main', None)
        return getattr(t, 'name', None) or getattr(t, 'username', '') if t else ''

    def get_room_name(self, obj):
        r = obj.room_override or getattr(obj.class_group, 'room_default', None)
        return getattr(r, 'name', '') if r else ''

    def validate(self, attrs):
        st = attrs.get('start_time') or getattr(self.instance, 'start_time', None)
        et = attrs.get('end_time') or getattr(self.instance, 'end_time', None)
        if st and et and st >= et:
            raise serializers.ValidationError('end_time 必须晚于 start_time')
        wd = attrs.get('weekday') or getattr(self.instance, 'weekday', None)
        if wd and (wd < 1 or wd > 7):
            raise serializers.ValidationError('weekday 取值范围 1~7')
        return attrs

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)