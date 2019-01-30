import  logging
logger = logging.getLogger(__name__)


class BaseIntegrator(object):

    # This method check if the user area is serviceable by the integrator or not.
    def get_is_user_area_serviceable(self, pincode):
        try:
            is_serviceable = self._get_is_user_area_serviceable(pincode)
            return is_serviceable
        except Exception as e:
            logger.error("[ERROR]" + self.__class__.__name__ + " get serviceable area error. " + str(e))

        return True

    # This method fetches the available timeslot from respective integrator according to the object.
    def get_appointment_slots(self, pincode, date, **kwargs):
        try:
            timeslot_dictionary = self._get_appointment_slots(pincode, date, **kwargs)
            return timeslot_dictionary
        except Exception as e:
            logger.error("[ERROR]" + self.__class__.__name__ + " get timeslot error. " + str(e))

        return {}

    def post_order(self, lab_appointment):
        try:
            order_detail = self._post_order_details(lab_appointment)
            return order_detail
        except Exception as e:
            logger.error("[ERROR]" + self.__class__.__name__ + " order booking error. " + str(e))

        return None

    def list_orders(self):
        pass

    def pull_reports(self):
        pass

    def order_details(self):
        pass

    def get_pricing(self):
        pass
