from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Assignment, Attempt, AuditLog, Batch, College, ConsentRecord, DataRequest, Enrollment, Experiment, User


@admin.register(User)
class MyUserAdmin(UserAdmin):
    list_display = ('username', 'first_name', 'last_name', 'role', 'college', 'roll_no', 'email_verified', 'is_active', 'last_login')
    list_filter = ('role', 'college', 'is_active', 'email_verified')
    search_fields = ('username', 'first_name', 'last_name', 'roll_no', 'email')
    fieldsets = UserAdmin.fieldsets + (('XPRISM', {'fields': ('role', 'college', 'roll_no', 'must_change_password', 'consent_version', 'consent_at', 'failed_logins', 'locked_until', 'anonymised', 'email_verified', 'email_verified_at')}),)
    add_fieldsets = UserAdmin.add_fieldsets + (('XPRISM', {'fields': ('role', 'college', 'roll_no')}),)


@admin.register(College)
class CollegeAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'created_at')
    filter_horizontal = ('disabled_experiments',)


@admin.register(Experiment)
class ExperimentAdmin(admin.ModelAdmin):
    list_display = ('no', 'title', 'semester', 'category', 'is_active')
    list_editable = ('is_active',)


class EnrollmentInline(admin.TabularInline):
    model = Enrollment
    extra = 0
    raw_id_fields = ('student',)


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ('name', 'college', 'academic_year', 'class_code', 'archived')
    list_filter = ('college', 'archived')
    filter_horizontal = ('faculty',)
    inlines = [EnrollmentInline]


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ('experiment', 'batch', 'due_at', 'exam_mode', 'max_marks')
    list_filter = ('exam_mode', 'batch__college')


@admin.register(Attempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = ('student', 'assignment', 'status', 'auto_score', 'manual_marks', 'submitted_at')
    list_filter = ('status',)
    raw_id_fields = ('student', 'assignment', 'graded_by')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('at', 'actor', 'college', 'action', 'target', 'ip')
    list_filter = ('action', 'college')
    def has_change_permission(self, request, obj=None): return False
    def has_add_permission(self, request): return False


admin.site.register(ConsentRecord, list_display=('user', 'policy_version', 'accepted_at'))
admin.site.register(DataRequest, list_display=('username_snapshot', 'kind', 'status', 'created_at'))
