constants = {
    'QC_GROUP_NAME': 'qc_group',
    'DOCTOR_NETWORK_GROUP_NAME': 'doctor_network_team',
    'LAB_PRICING_GROUP_NAME': 'lab_pricing_team',
    'CAREERS_MANAGEMENT_GROUP': 'careers_management_group',
    'ONLINE_LEADS_GROUP': 'online_leads_group',
    'ABOUT_DOCTOR_TEAM': 'about_doctor_team',
    'ARTICLE_TEAM': 'article_team',
    'DOCTOR_MAPPING_TEAM': 'doctor_mapping_team',
    'DOCTOR_IMAGE_CROPPING_TEAM': 'doctor_image_cropping_team',
    'TEST_USER_GROUP': 'test_user_group',
    'OPD_APPOINTMENT_MANAGEMENT_TEAM': 'opd_appointment_management_team',
    'LAB_APPOINTMENT_MANAGEMENT_TEAM': 'lab_appointment_management_team',
    'SALES_CALLING_TEAM': 'sales_calling_team',
    'CONDITIONS_MANAGEMENT_TEAM': 'condition_managment_team',
    'REPORT_TEAM': 'report_team',
    'SUPER_QC_GROUP': 'super_qc_group',
    'DATA_EXPORT_GROUP': 'data_export',
    'DOCTOR_SALES_GROUP': 'doctor_sales_group',
    'REVIEW_TEAM_GROUP': 'review_team_group',
    'ELASTIC_TEAM': 'elastic_team',
    'PROCEDURE_TEAM': 'procedure_team',
    'COUPON_MANAGEMENT_GROUP': 'coupon_group',
    'LAB_TEST_TEAM': 'lab_test_team',
    'MERCHANT_TEAM': 'merchant_team',
    'COMMENT_TEAM': 'comment_team',
    'PRODUCT_TEAM': 'product_team',
    'INTEGRATION_MANAGEMENT_TEAM': 'integration_management_team',
    'WELCOME_CALLING_TEAM': 'welcome_calling_team',
    'DOC_AVAILABILITY_TEAM_GROUP': 'doctor_availability_team',
    'APPOINTMENT_OTP_TEAM': 'appointment_otp_team',
    'INSURANCE_GROUP': 'insurance_group',
    'APPOINTMENT_REFUND_TEAM': 'appointment_refund_team',
    'SUPER_INSURANCE_GROUP': 'super_insurance_group',
    'IPD_TEAM': 'ipd_team',
    'CORPORATE_GROUP' : 'corporate_group',
    'BLOCK_STATE_GROUP': 'block_state_group',
    'BLOCK_USER_GROUP': 'block_user_group',
    'APPOINTMENT_OTP_BYPASS_AGENT_TEAM': 'appointment_otp_bypass_agent_team',
    'MARKETING_INTERN': 'marketing_intern',
    'USER_UPDATE_TEAM': 'user_update_team',
    'QC_MERCHANT_TEAM': 'qc_merchant_team',
    'POC_TEAM': 'poc_team',
    'COMMUNICATION_TEAM': 'communication_team',
    'PLUS_TEAM': 'plus_team',
    'PARTNER_LAB_TEAM': 'partner_lab_team'
}
matrix_product_ids = {
    'opd_products': 1,
    'lab_products': 4,
    'consumer': 5,
    'ipd_procedure': 9
}
matrix_subproduct_ids = {
    "chat": 1,
    "appointment": 2,
    "insurance": 3,
    "other_services": 4,
    "doctor": 8,
    "hospital": 7,
    "hospitalnetwork": 6
}
matrix_status = {
    'NEW': 1,
    'COST_REQUESTED': 28,
    'COST_SHARED': 29,
    'OPD': 30,
    'NOT_INTERESTED': 4,
    'COMPLETED': 19,
    'VALID': 2,
    'CONTACTED': 3,
    'PLANNED': 31,
    'IPD_CONFIRMATION': 32,
}
matrix_status_to_ipd_lead_status_mapping = {
    matrix_status['NEW']: 1,
    matrix_status['COST_REQUESTED']: 2,
    matrix_status['COST_SHARED']: 3,
    matrix_status['OPD']: 4,
    matrix_status['NOT_INTERESTED']: 5,
    matrix_status['COMPLETED']: 6,
    matrix_status['VALID']: 7,
    matrix_status['CONTACTED']: 8,
    matrix_status['PLANNED']: 9,
    matrix_status['IPD_CONFIRMATION']: 10,
}



PREPAID = 1
COD = 2
INSURANCE = 3
PLAN = 4
VIP = 5
PAY_CHOICES = ((PREPAID, 'Prepaid'), (COD, 'COD'), (INSURANCE, 'Insurance'), (PLAN, "Subscription Plan"),
                    (VIP, 'VIP'))
