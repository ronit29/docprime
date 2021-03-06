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
    LAB_DISCOUNT = 'LAB_DISCOUNT'
    LABTEST_AMOUNT = 'LABTEST_AMOUNT'
    LABTEST_COUNT = 'LABTEST_COUNT'
    PACKAGE_DISCOUNT = 'PACKAGE_DISCOUNT'
    TOTAL_WORTH = 'TOTAL_WORTH'
    DOCTOR_MINIMUM_CAPPING_AMOUNT = 'DOCTOR_MINIMUM_CAPPING_AMOUNT'
    DOCTOR_MAXIMUM_CAPPING_AMOUNT = 'DOCTOR_MAXIMUM_CAPPING_AMOUNT'
    DOCTOR_CONVENIENCE_PERCENTAGE = 'DOCTOR_CONVENIENCE_PERCENTAGE'
    LAB_MINIMUM_CAPPING_AMOUNT = 'LAB_MINIMUM_CAPPING_AMOUNT'
    LAB_MAXIMUM_CAPPING_AMOUNT = 'LAB_MAXIMUM_CAPPING_AMOUNT'
    LAB_CONVENIENCE_PERCENTAGE = 'LAB_CONVENIENCE_PERCENTAGE'
    DOCTOR_MAX_DISCOUNTED_AMOUNT = 'DOCTOR_MAX_DISCOUNTED_AMOUNT'
    LAB_MAX_DISCOUNTED_AMOUNT = 'LAB_MAX_DISCOUNTED_AMOUNT'
    PACKAGE_MAX_DISCOUNTED_AMOUNT = 'PACKAGE_MAX_DISCOUNTED_AMOUNT'
    DOCTOR_MIN_DISCOUNTED_AMOUNT = 'DOCTOR_MIN_DISCOUNTED_AMOUNT'
    LAB_MIN_DISCOUNTED_AMOUNT = 'LAB_MIN_DISCOUNTED_AMOUNT'
    PACKAGE_MIN_DISCOUNTED_AMOUNT = 'PACKAGE_MIN_DISCOUNTED_AMOUNT'


class UtilizationCriteria(Choices):
    AMOUNT = "AMOUNT"
    COUNT = "COUNT"
    DISCOUNT = "DISCOUNT"


class UsageCriteria(Choices):
    AMOUNT_COUNT = "AMOUNT_COUNT"
    COUNT_DISCOUNT = "COUNT_DISCOUNT"
    AMOUNT_DISCOUNT = "AMOUNT_DISCOUNT"
    TOTAL_WORTH = "TOTAL_WORTH"
    TOTAL_WORTH_WITH_DISCOUNT = "TOTAL_WORTH_WITH_DISCOUNT"


class PriceCriteria(Choices):
    MRP = "MRP"
    DEAL_PRICE = "DEAL_PRICE"
    AGREED_PRICE = "AGREED_PRICE"
    COD_DEAL_PRICE = "COD_DEAL_PRICE"
