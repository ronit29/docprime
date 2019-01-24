class BaseIntegrator(object):

    # This method check if the user area is serviceable by the integrator or not.
    def get_is_user_area_serviceable(self, pincode):
        try:
            is_serviceable = self._get_is_user_area_serviceable(pincode)
            return is_serviceable
        except Exception as e:
            pass

        return True

    # This method fetches the available timeslot from respective integrator according to the object.
    def get_appointment_slots(self):
        try:
            timeslot_dictionary = self._get_appointment_slots()
            return timeslot_dictionary
        except Exception as e:
            pass

        return {}

    def post_order(self):
        pass

    def list_orders(self):
        pass

    def pull_reports(self):
        pass

    def order_details(self):
        pass
