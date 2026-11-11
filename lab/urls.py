from django.contrib.auth import views as auth_views
from django.urls import path, re_path

from . import views_admin as adm
from . import views_auth as au
from . import views_mailbox as mb
from . import views_public as pub
from . import views_staff as st
from . import views_student as stu

urlpatterns = [
    path('', pub.landing, name='landing'),
    path('index.html', pub.index_redirect),
    path('modules/', pub.modules, name='modules'),
    path('documentation/', pub.documentation, name='documentation'),
    path('home/', au.home, name='home'),
    path('healthz', pub.healthz),
    path('contact/', pub.contact, name='contact'),
    path('robots.txt', pub.robots_txt, name='robots_txt'),
    path('sitemap.xml', pub.sitemap_xml, name='sitemap_xml'),
    re_path(r'^experiments/(?P<slug>[a-z0-9-]+)(?:\.html)?$', pub.experiment_page, name='experiment'),
    path('subscribe/', pub.subscribe, name='subscribe'),
    path('api/free-year/apply', pub.free_year_apply, name='free_year_apply'),
    path('invitation/opt-out/<str:token>/', pub.invitation_opt_out, name='invitation_opt_out'),
    path('ethics/', pub.legal, {'page': 'ethics'}, name='ethics'),
    path('about/', pub.legal, {'page': 'about'}, name='about'),
    path('agreement/', au.ethics_agreement, name='ethics_agreement'),
    path('accounts/trial/', au.trial_signup, name='trial_signup'),
    path('platform/trials/', adm.trial_users, name='trial_users'),
    path('privacy/', pub.legal, {'page': 'privacy'}, name='privacy'),
    path('terms/', pub.legal, {'page': 'terms'}, name='terms'),
    path('conditions/', pub.legal, {'page': 'conditions'}, name='conditions'),

    # accounts
    path('accounts/login/', au.login_view, name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('accounts/signup/', au.signup, name='signup'),
    path('accounts/verify/resend/', au.resend_verification, name='resend_verification'),
    path('accounts/verify/<uidb64>/<token>/', au.verify_email, name='verify_email'),
    path('consent/', au.consent, name='consent'),
    path('accounts/password/force/', au.force_password, name='force_password'),
    path('accounts/password/change/', au.force_password, name='password_change'),
    path('accounts/password/reset/', auth_views.PasswordResetView.as_view(template_name='registration/reset_form.html', email_template_name='registration/reset_email.txt', subject_template_name='registration/reset_subject.txt'), name='password_reset'),
    path('accounts/password/reset/sent/', auth_views.PasswordResetDoneView.as_view(template_name='registration/reset_done.html'), name='password_reset_done'),
    path('accounts/password/reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='registration/reset_confirm.html'), name='password_reset_confirm'),
    path('accounts/password/reset/complete/', auth_views.PasswordResetCompleteView.as_view(template_name='registration/reset_complete.html'), name='password_reset_complete'),
    path('me/data/', au.my_data, name='my_data'),

    # student
    path('student/', stu.dashboard, name='student_dashboard'),
    path('student/assignments/<int:pk>/', stu.assignment, name='student_assignment'),
    path('api/attempts/<int:pk>/submit', stu.api_submit, name='api_submit'),
    path('api/experiments/<slug:slug>/feedback', stu.api_feedback, name='api_feedback'),
    path('feedback/', st.feedback_overview, name='feedback_overview'),

    # faculty / lab assistant / college admin
    path('faculty/', st.dashboard, name='staff_dashboard'),
    path('faculty/batches/', st.batch_list, name='batch_list'),
    path('faculty/batches/new/', st.batch_form, name='batch_new'),
    path('faculty/batches/<int:pk>/', st.batch_detail, name='batch_detail'),
    path('faculty/batches/<int:pk>/edit/', st.batch_form, name='batch_edit'),
    path('faculty/batches/<int:pk>/action/<str:action>/', st.batch_action, name='batch_action'),
    path('faculty/batches/<int:pk>/students/add/', st.student_add, name='student_add'),
    path('faculty/batches/<int:pk>/students/upload/', st.students_upload, name='students_upload'),
    path('faculty/batches/<int:pk>/students/credentials.csv', st.credentials_download, name='credentials_download'),
    path('faculty/batches/<int:pk>/students/<int:user_id>/<str:action>/', st.student_action, name='student_action'),
    path('faculty/batches/<int:pk>/marks/', st.marks_sheet, name='marks_sheet'),
    path('faculty/batches/<int:batch_pk>/assignments/new/', st.assignment_form, name='assignment_new'),
    path('faculty/assignments/<int:pk>/', st.assignment_detail, name='assignment_detail'),
    path('faculty/assignments/<int:pk>/edit/', st.assignment_form, name='assignment_edit'),
    path('faculty/assignments/<int:pk>/delete/', st.assignment_delete, name='assignment_delete'),
    path('faculty/attempts/<int:pk>/', st.attempt_detail, name='attempt_detail'),

    # college admin
    path('college/', adm.college_dashboard, name='college_dashboard'),
    path('college/users/', adm.staff_users, name='staff_users'),
    path('college/users/<int:user_id>/<str:action>/', adm.user_action, name='user_action'),
    path('college/experiments/', adm.college_experiments, name='college_experiments'),
    path('college/settings/', adm.college_settings, name='college_settings'),
    path('college/audit/', adm.audit_log, name='audit_log'),
    path('college/requests/', adm.data_requests, name='data_requests'),

    # platform
    path('platform/', adm.platform_dashboard, name='platform_dashboard'),
    path('platform/colleges/', adm.college_list, name='college_list'),
    path('platform/colleges/new/', adm.college_form, name='college_new'),
    path('platform/colleges/<int:pk>/', adm.college_form, name='college_edit'),
    path('platform/experiments/', adm.platform_experiments, name='platform_experiments'),
    path('platform/contact/', adm.contact_requests, name='contact_requests'),
    path('platform/mailbox/', mb.mailbox_list, name='mailbox'),
    path('platform/mailbox/compose/', mb.mailbox_compose, name='mailbox_compose'),
    path('platform/mailbox/preview/', mb.mailbox_preview, name='mailbox_preview'),
    path('platform/mailbox/<int:pk>/', mb.mailbox_message, name='mailbox_message'),
    path('platform/free-year/', adm.free_year_applications, name='free_year_applications'),
    path('platform/free-year/invite/', adm.free_year_invitations, name='free_year_invitations'),
]
