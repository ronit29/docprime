from ondoc.common.helper import Choices


class PlanParametersEnum(Choices):
    DOCTOR_CONSULT_AMOUNT = 'DOCTOR_CONSULT_AMOUNT'
    ONLINE_CHAT_AMOUNT = 'ONLINE_CHAT_AMOUNT'
    HEALTH_CHECKUPS_AMOUNT = 'HEALTH_CHECKUPS_AMOUNT'
    DOCTOR_CONSULT_COUNT = 'DOCTOR_CONSULT_COUNT'
    ONLINE_CHAT_COUNT = 'ONLINE_CHAT_COUNT'
    HEALTH_CHECKUPS_COUNT = 'HEALTH_CHECKUPS_COUNT'
    PACKAGES_COVERED = 'PACKAGES_COVERED'
    SPECIALIZATIONS = 'SPECIALIZATIONS'
    PERCENTAGE_DISCOUNT = 'PERCENTAGE_DISCOUNT'
    MEMBERS_COVERED_IN_PACKAGE = 'MEMBERS_COVERED_IN_PACKAGE'
    TOTAL_TEST_COVERED_IN_PACKAGE = 'TOTAL_TEST_COVERED_IN_PACKAGE'
    PACKAGE_IDS = 'PACKAGE_IDS'
    DOCTOR_CONSULT_DISCOUNT = 'DOCTOR_CONSULT_DISCOUNT'


class UtilizationCriteria(Choices):
    AMOUNT = "AMOUNT"
    COUNT = "COUNT"
