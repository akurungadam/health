frappe.listview_settings["Imaging Appointment"] = {
	filters: [["status", "=", "Open"]],
	get_indicator: function(doc) {
		var colors = {
			"Scheduled": "orange",
			"In Progress": "red",
			"Completed": "green",
		};
		return [__(doc.status), colors[doc.status], "status,=," + doc.status];
	}
};
