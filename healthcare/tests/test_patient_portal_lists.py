import frappe

from healthcare.healthcare.doctype.patient_appointment.test_patient_appointment import create_appointment
from healthcare.healthcare.web_form.lab_test.lab_test import get_lab_test_list
from healthcare.healthcare.web_form.patient_appointments.patient_appointments import get_appointment_list
from healthcare.healthcare.web_form.prescription.prescription import get_encounter_list
from healthcare.tests.factories.encounters import create_encounter
from healthcare.tests.utils import HealthcareTestSuite

PORTAL_USER = "web_form_patient@marleyhealth.io"
PORTAL_PATIENT = "_Test Web Form Patient"
PRACTITIONER = "_Test Healthcare Practitioner 2"
LIST_FUNCTIONS = (get_encounter_list, get_appointment_list, get_lab_test_list)


class TestPatientPortalLists(HealthcareTestSuite):
	def test_encounters_list_only_the_users_own(self):
		own = create_encounter(PORTAL_PATIENT, PRACTITIONER)
		other = create_encounter("_Test Patient", PRACTITIONER)

		names = self.list_names(get_encounter_list)

		self.assertIn(own.name, names)
		self.assertNotIn(other.name, names)

	def test_appointments_list_only_the_users_open_ones(self):
		own = create_appointment(PORTAL_PATIENT, PRACTITIONER, appointment_time="09:00:00")
		other = create_appointment("_Test Patient", PRACTITIONER, appointment_time="11:00:00")

		names = self.list_names(get_appointment_list)

		self.assertIn(own.name, names)
		self.assertNotIn(other.name, names)

	def test_a_user_without_a_patient_sees_nothing(self):
		create_encounter("_Test Patient", PRACTITIONER)
		with self.set_user("test_user@marleyhealth.io"):
			for list_function in LIST_FUNCTIONS:
				self.assertEqual(list_function("Patient Encounter", "", {}, 0), [])

	def list_names(self, list_function):
		with self.set_user(PORTAL_USER):
			return [row.name for row in list_function(None, "", {}, 0)]
