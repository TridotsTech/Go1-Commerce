// Copyright (c) 2016, sivaranjani and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Vendor Order"] = {
	"filters": [
	{
			"fieldname":"from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.add_months(frappe.datetime.get_today(),-1),
			"reqd": 1
		},
		{
			"fieldname":"to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 1
		},
		{
			"fieldname":"status",
			"label":__("Order Status"),
			"fieldtype":"Select",
			"options":"\nPlaced\nProcessing\nCompleted\nCancelled"			
		},
		{
			"fieldname":"payment_status",
			"label":__("Payment Status"),
			"fieldtype":"Select",
			"options":"\n Pending\nPaid\nCancelled"			
		}
		

	]
}
