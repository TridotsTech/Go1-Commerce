from __future__ import unicode_literals, print_function
import frappe,json
from frappe import _
from frappe.utils import flt, getdate,nowdate
from datetime import datetime
from six import string_types
from go1_commerce.utils.setup import get_settings
from go1_commerce.utils.utils import \
	role_auth,customer_reg_auth,get_auth_token,get_customer_from_token,\
	other_exception,authentication_exception,doesnotexist_exception,\
	permission_exception,validation_exception
from frappe.query_builder import DocType, Field, Order

@frappe.whitelist(allow_guest = True)
def login(usr,pwd):
	try:
		frappe.local.login_manager.authenticate(usr, pwd)
		frappe.local.login_manager.post_login()
		login_response = {'message': frappe.local.response['message']}
		token = get_auth_token(usr)
		if token and token.get("api_secret"):
			has_role = frappe.db.get_all('Has Role',filters={'parent': usr, 'role': "Customer"})
			if has_role:
				Customers = DocType('Customers')
				customer = (frappe.qb.from_(Customers)
							  .select(Customers.customer_status)
							  .where(Customers.email == usr)
						   ).run(as_dict=True)
				
				if customer[0].customer_status != "Approved":
					frappe.local.response.http_status_code = 200
					frappe.local.response.status = "Failed"
					frappe.local.response.message = "You account not yet verified.You will get notified once verfied."
				else:
					login_response['api_key'] = token['api_key']
					login_response['api_secret'] = token['api_secret']
					login_response['status'] = "success"
					return login_response
			else:
				frappe.local.response.http_status_code = 500
				frappe.local.response.status = "Failed"
				frappe.local.response.message = "You dont have access."
		else:
			login_response.update(token)
			return login_response
	except frappe.exceptions.AuthenticationError:
		authentication_exception()
	except Exception:
		other_exception("Error in customer login")

def get_list_period_wise(dt, customer_id):
	from frappe.query_builder.functions import CustomFunction
	Doc = DocType(dt)
	YEARWEEK = CustomFunction('YEARWEEK', ['field', 'mode'])
	MONTH = CustomFunction('MONTH', ['field'])
	CURDATE = CustomFunction('CURDATE', [])
	DATE = CustomFunction('DATE', ['field'])
	week_order_list = (frappe.qb.from_(Doc)
						.select(Doc.name)
						.where(Doc.customer == customer_id)
						.where(YEARWEEK(Doc.creation, 1) == YEARWEEK(CURDATE(), 1))
						.where(Doc.naming_series != "SUB-ORD-")
						
					  ).run(as_dict=True)
	month_order_list = (frappe.qb.from_(Doc)
						 .select(Doc.name)
						 .where(Doc.customer == customer_id)
						 .where(MONTH(Doc.creation) == MONTH(CURDATE()))
						 .where(Doc.naming_series != "SUB-ORD-")
						
					   ).run(as_dict=True)
	today_order_list = (frappe.qb.from_(Doc)
						 .select(Doc.name)
						 .where(Doc.customer == customer_id)
						 .where(DATE(Doc.creation) == CURDATE())
						 .where(Doc.naming_series != "SUB-ORD-")
						 
					   ).run(as_dict=True)
	all_order_list = (frappe.qb.from_(Doc)
					   .select(Doc.name)
					   .where(Doc.customer == customer_id)
					   .where(Doc.naming_series != "SUB-ORD-")
					  
					 ).run(as_dict=True)

	return [week_order_list, month_order_list, today_order_list, all_order_list]

@frappe.whitelist()
def get_customer_dashboard(customer_id=None):
	try:
		if not customer_id:
			customer_id = get_customer_from_token()
		if customer_id:
			recent_orders = get_orders_list(page_no = 1,page_length = 5, no_subscription_order = 1)
			
			dt = 'Order'
			data = get_list_period_wise(dt,customer_id)
			week_order_list = data[0]
			month_order_list = data[1]
			today_order_list = data[2]
			all_order_list = data[3]
			return {"status":"success","data":{"all_count":len(all_order_list),
					"monthly_count": len(month_order_list),
					"today_orders_count": len(today_order_list),"recent_orders":recent_orders,
					"week_orders_count":len(week_order_list)}}
		else:
			return {"status":"failed","message":"Customer not found."}
	except Exception:
		other_exception("Error in go1_commerce.v2.customer")
		return {"status":"failed","message":"Something Went Wrong."}


def check_condition_in_order_list(customer,status,driver,date,shipping_method,
								  no_subscription_order,order_from,exclude_order_from,allow_draft, language):
	condition = ''
	if customer:
		condition += ' and customer = "{0}"'.format(customer)
	if status and status == 'Pending':
		condition += ' and status not in ("Completed", "Cancelled")'
	if driver:
		condition += ' and driver = "{0}"'.format(driver)
	if date:
		condition += ' and order_date = "{0}"'.format(getdate(date))
	if shipping_method:
		condition += ' and (shipping_method = "{0}" or shipping_method_name = "{0}")'.\
						format(shipping_method)
	if not language:
		language = frappe.get_system_settings('language')
	if no_subscription_order:
		condition += ' and naming_series != "SUB-ORD-"'
	if order_from:
		condition += ' and order_from = "{0}"'.format(order_from)
	if exclude_order_from:
		condition += ' and order_from <> "{0}"'.format(exclude_order_from)
	if not allow_draft:
		condition += ' and docstatus > 0'

	return condition

@frappe.whitelist()
def get_orders_list(page_no=1,page_length=10,no_subscription_order=0,order_from=None,language=None,
					status=None,shipping_method=None,date=None,driver=None,allow_draft=1,
					exclude_order_from=None, customer=None):
	try:
		
		if not customer:
			customer = get_customer_from_token()
		
		Orders = DocType("Order")
		query = frappe.qb.from_(Orders).select('*').where(Orders.total_amount > 0)
		if customer:
			query = query.where(Orders.customer == customer)
		if status and status == 'Pending':
			query = query.where(Orders.status.notin(["Completed", "Cancelled"]))
		if driver:
			query = query.where(Orders.driver == driver)
		if date:
			query = query.where(Orders.order_date == getdate(date))
		if shipping_method:
			query = query.where((Orders.shipping_method == shipping_method) | (Orders.shipping_method_name == shipping_method))
		if no_subscription_order:
			query = query.where(Orders.naming_series != "SUB-ORD-")
		if order_from:
			query = query.where(Orders.order_from == order_from)
		if exclude_order_from:
			query = query.where(Orders.order_from != exclude_order_from)
		if not allow_draft:
			query = query.where(Orders.docstatus > 0)
		query = query.orderby(Orders.creation, order=Order.desc)
		query = query.limit(page_length).offset((int(page_no) - 1) * int(page_length))
		orders = query.run(as_dict=True)
		orders = get_orders_items(orders)
		return orders
	except Exception:
		other_exception("Error in v2.customer.get_orders_list")

def get_orders_items(orders):
	get_time_log = 1
	if orders:
		
		for item in orders:
			order_item_qty=0
			OrderItem = DocType("Order Item")
			query = (frappe.qb.from_(OrderItem).select("*").where(OrderItem.parent == item.name))
			item.items = query.run(as_dict=True)

			for it in item['items']:
				if it.quantity:
					order_item_qty += it.quantity
				if it.return_created==1:
					if it.shipping_status == "Pending":
						it.return_status = "Request Pending"
					if it.shipping_status == "Approved":
						it.return_status = "Request Approved"
					if it.shipping_status == "Shipped":
						it.return_status = "Request Shipped"
					if it.shipping_status == "Delivered":
						it.return_status = "Request Delivered"
					if it.shipping_status == "Rejected":
						it.return_status = "Request Rejected"
			item.status_history=[]
			PaymentEntry = DocType("Payment Entry")
			PaymentReference = DocType("Payment Reference")
			query = (frappe.qb.from_(PaymentEntry)
				.distinct()
				.select(PaymentEntry.mode_of_payment)
				.left_join(PaymentReference)
				.on(PaymentEntry.name == PaymentReference.parent)
				.where(PaymentReference.reference_doctype == "Order")
				.where(PaymentReference.reference_name == item.name))
			payment_entry = query.run(as_list=True)
			if payment_entry:
				item.payment_modes = payment_entry
			else:
				item.payment_modes = [item.payment_method]
			item.tax_rate = get_order_tax(item)
			item.checkout_attributes = frappe.db.get_all('Order Checkout Attributes',
											fields=['attribute_description','price_adjustment'],
											filters={'parent': item.name})
			if frappe.db.get_value('Payment Method', item.payment_method):
				item.payment_option = frappe.db.get_value('Payment Method',item.payment_method, 'payment_type')
			if item.get('driver'):
				item.driver_phone = frappe.db.get_value('Drivers', item.driver, 'driver_phone')
			if item.docstatus == 2:
				item.status = "Cancelled"
			item.delivery_slot_list = get_order_delivery_slots(item)	
			item.pay_status, item.redirect_url = get_order_payment_info(item)
			item.total_item_qty = order_item_qty
	return orders

def get_order_tax(item):
	try:
		tax_rate = 0
		if item.tax_breakup:
			tax_list = item.tax_breakup.split('\n')
			for tax in tax_list:
				if tax:
					tax_type = tax.split(' - ')
					if tax_type[1] and len(tax_type) == 4:
						tax_rate = tax_rate + float(tax_type[1].split('%')[0])


		try:
			tax_rate = int(tax_rate) if (tax_rate).is_integer() else tax_rate
		except Exception as e:
			tax_rate = int(tax_rate)
		return tax_rate
	except Exception as e:
		return 0

def get_order_payment_info(item):
	payment_method = item.payment_method
	pay_status = 1
	redirect_url=""
	if payment_method:
		payment_type = None
		redirectController=None
		if frappe.db.get_value('Payment Method', item.payment_method):
			payment_method_info = frappe.get_doc('Payment Method',payment_method)
			payment_type = payment_method_info.payment_type
			redirectController = payment_method_info.redirect_controller
		if payment_type and payment_type!='Cash':
			if item.docstatus==0:
				redirect_url="/"+str(redirectController)+"?order_id="+str(item.name)
				redirect_url = redirect_url
				pay_status=0
	return pay_status, redirect_url
				
def get_order_delivery_slots(item):
	delivery_slot = frappe.db.get_all('Order Delivery Slot',
					fields=['order_date', 'from_time', 'to_time','product_category'],
					filters={'order': item.name})
	delivery_slot_list = []
	if delivery_slot:
		for x in delivery_slot:
			from_dt = datetime.strptime(str(getdate(x.order_date)) + ' ' +
					  str(x.from_time), '%Y-%m-%d %H:%M:%S')
			to_dt = datetime.strptime(str(getdate(x.order_date)) + ' ' +
					str(x.to_time), '%Y-%m-%d %H:%M:%S')
			category = ''
			if x.product_category:
				category = frappe.get_value('Product Category', x.product_category, 
						   'category_name')
			delivery_slot = {
							'order_date': x.order_date,
							'from_time': x.from_time,
							'to_time': x.to_time,
							'format_date': getdate(x.order_date).strftime('%b %d, %Y'),
							'format_from_time': from_dt.strftime('%I:%M %p'),
							'format_to_time': to_dt.strftime('%I:%M %p'),
							'category':category,
							}
			delivery_slot_list.append(delivery_slot)
	return delivery_slot_list
		
@frappe.whitelist()
def get_customer_address(customer_id=None):
	try:
		if not customer_id:
			customer_id = get_customer_from_token()
		if customer_id:
			CustomerAddress = DocType('Customer Address')
			query = (
				frappe.qb.from_(CustomerAddress)
				.select('*')
				.where(CustomerAddress.parent == customer_id)
				.orderby(
					CustomerAddress.is_default,
					CustomerAddress.name
				)
			)
			addresses = query.run(as_dict=True)
			return addresses
		else:
			return {"status":"failed","message":"Customer not found."}
	except Exception:
		other_exception("Error in v2.customer.get_customer_address")

@frappe.whitelist()
def get_customer_order_list(page_no = None, page_length = None, customer_id=None):
	try:
		if type(page_no) == int and type(page_length) == int and page_no and page_length:
			if not customer_id:
				customer_id = get_customer_from_token()
			if customer_id:
				limit_start = (int(page_no)-1) * int(page_length)
				fields_list = ["name","creation","status","payment_status","total_amount"]
				order = frappe.get_all('Order', 
								filters={'customer': customer_id,'naming_series': ('!=','SUB-ORD-')},
								fields=fields_list, limit_start=limit_start, 
								limit_page_length=page_length, order_by='creation desc')
				if order:
					for i in order:
						order_items = frappe.get_all('Order Item', fields=['name','item'],
													filters={'parent': i.name})
						i.Items = order_items
				return order
			else:
				return {"status":"failed",
						"message":"Customer not found."}
		else:
			return {"status":"failed",
					"message":"Please send valid page_no and page_length."}
	except Exception:
		other_exception("Error in v2.customer.get_customer_order_list")

@frappe.whitelist()
def get_customer_order_details(order_id, customer_id=None):
	try:
		if not customer_id:
			customer_id = get_customer_from_token()
		if customer_id and frappe.db.get_all("Order",filters={"name":order_id,"customer":customer_id}):
			order = frappe.get_doc('Order', order_id)
			delivery_slot = []
			check_slot = frappe.db.get_all('Order Delivery Slot',filters={'order': order_id},
								fields=['order_date', 'from_time', 'to_time', 'product_category'])
			if check_slot:
				for deli_slot in check_slot:
					category = ''
					if deli_slot.product_category:
						category = frappe.get_value('Product Category',deli_slot.product_category, 'category_name')
					from_time = datetime.strptime(str(deli_slot.from_time),'%H:%M:%S').time()
					to_time = datetime.strptime(str(deli_slot.to_time),'%H:%M:%S').time()
					delivery_slot.append({'delivery_date': deli_slot.order_date.strftime('%b %d, %Y'),
											'from_time'   : from_time.strftime('%I:%M %p'),
											'to_time'     : to_time.strftime('%I:%M %p'),
											'category'    : category})
			return {"info":order,"delivery_slot":delivery_slot}
		else:
			return {"status":"failed","message":"Customer not found."}
	except Exception:
		other_exception("Error in v2.customer.get_customer_order_details")


@frappe.whitelist()
def update_password(new_password, logout_all_sessions=0, key=None, old_password=None, user=None):
	try:
		from go1_commerce.go1_commerce.doctype.order_settings.order_settings import validate_password
		from frappe.utils.password import update_password as _update_password
		password_res = validate_password(new_password)
		if password_res.get("status") == "Success":
			if not user:
				user = frappe.session.user
			if not key:
				from frappe.utils import random_string
				key = random_string(32)
				if user:
					frappe.db.set_value('User', user, 'reset_password_key', key)
			res = _get_user_for_update_password(key,new_password, old_password, user)
			if res.get('message'):
				return res['message']
			else:
				user = res['user']
			_update_password(user, new_password, logout_all_sessions=int(logout_all_sessions))
			redirect_to = frappe.cache().hget('redirect_after_login', user)
			if redirect_to:
				frappe.cache().hdel('redirect_after_login', user)
			frappe.local.login_manager.login_as(user)
			return {"status":"Success"}
		else:
			return password_res
	except Exception:
		other_exception("Error in v2.customer.update_password")
		return {"status":"Failed"}


def reset_user_data(user):
	user_doc = frappe.get_doc('User', user)
	redirect_url = user_doc.redirect_url
	user_doc.reset_password_key = ''
	user_doc.redirect_url = ''
	user_doc.save(ignore_permissions=True)
	return (user_doc, redirect_url)


def _get_user_for_update_password(key,new_password, old_password, user):
	if key:
		user = frappe.db.get_value('User',{'reset_password_key': key})
		if not user:
			return {'message': _('Cannot Update: Incorrect / Expired Link.')}
	elif old_password:
		frappe.local.login_manager.check_password(user,old_password)
		user = frappe.session.user
	else:
		return {"message":"old password is missing."}
	return {'user': user}


@frappe.whitelist()
def update_address(data):
	try:
		response = json.loads(data)
		if not response.get('customer'):
			customer = get_customer_from_token()
		else:
			customer = response.get('customer')
		if customer:
			if response.get('is_default') == 1:
				set_default_address(customer)
			if response.get('address_type'):
				res = validate_address(response.get('address_type'), customer,response.get('name'))
				if res and res['status'] == 'failed':
					return res
			address = frappe.get_doc('Customer Address', response.get('name'))
			set_address_fields(response, address)
			address.save(ignore_permissions=True)
			return address.as_dict()
		else:
			return {"status":"failed","message":"Customer not found."}
	except Exception:
		other_exception("Error inv2.customer.update_address")
		

def set_default_address(customer_name):
	CustomerAddress = DocType("Customer Address")
	query = (frappe.qb.from_(CustomerAddress).select(CustomerAddress.name).where(
		CustomerAddress.parent == customer_name))
	existing_address = query.run(as_dict=True)
	for address in existing_address:
		addr = frappe.get_doc('Customer Address', address.name)
		addr.is_default = 0
		addr.save(ignore_permissions=True)

def set_address_fields(response, address):
	if response.get('first_name'):
		address.first_name = response.get('first_name')
	if response.get('last_name'):
		address.last_name = response.get('last_name')
	address.address    = response.get('addr1')
	address.city       = response.get('city')
	address.county     = response.get('district')
	address.is_default = response.get('is_default')
	address.state      = response.get('state')
	address.country    = response.get('country')
	address.zipcode    = response.get('pincode')
	address.phone      = response.get('phone')
	address.landmark   = response.get('landmark')
	if response.get('address_type'):
		address.address_type = response.get('address_type')
	if response.get('door_no'):
		address.door_no = response.get('door_no')
	if response.get('unit_number'):
		address.unit_number = response.get('unit_number')
	if response.get('latitude'):
		address.latitude = response.get('latitude')
	if response.get('longitude'):
		address.longitude = response.get('longitude')
	if response.get('house_type'):
		address.house_type = response.get('house_type')

@frappe.whitelist()
def get_customer_info(user=None, email=None, doctype=None, guest_id=None, phone=None, customer=None):
	try:
		if not customer:
			customer = get_customer_from_token()
		if customer:
			if not doctype:
				doctype = 'Customers'
			Customer = None
			filters = []
			if customer and customer != '':
				filters.append(['name','=', customer])
			elif email and email != '':
				if doctype == 'Customers':
						filters.append(['email','=', email])
				else:
					filters.append(['name', '=', email])
			elif phone and phone != '':
				if doctype == 'Customers':
					filters.append(['phone', '=', phone])
				elif doctype == 'Shop User':
					filters.append(['mobile_no', '=', phone])
			if len(filters) == 0:
				return {'status': 'failed', 
						'message': frappe._('Missing user details')}
		
			Customer = frappe.db.get_all(doctype, fields=['*'], filters=filters)
			
			if Customer:
				return set_customer(Customer,doctype,guest_id)
			else:
				return {"status":"failed",
						"message":"Customer details not found."}
		else:
			return {"status":"failed",
					"message":"Customer not found."}
	except Exception:
		other_exception("Error in v2.customer.get_customer_info")


def set_customer(Customer,doctype,guest_id):
	CustomerAddress = DocType("Customer Address")
	Customer[0].address = (
		frappe.qb.from_(CustomerAddress)
		.select("*")
		.where(CustomerAddress.parent == Customer[0].name)
		.run(as_dict=True)
	)
	if doctype == 'Customers':
		CustomerRole = DocType("Customer Role")
		roles_list = (
			frappe.qb.from_(CustomerRole)
			.select(CustomerRole.role)
			.where(CustomerRole.parent == Customer[0].name).run(as_dict=True)
		)
		
		if not roles_list or len(roles_list) == 0: roles_list = ['Customer']
		Customer[0].roles_list = roles_list
	if guest_id and Customer[0].name != guest_id:
		move_cart_items(Customer[0].name, guest_id)
	token = get_auth_token(Customer[0].email)
	if token:
		Customer[0].api_key = token['api_key']
		Customer[0].api_secret = token['api_secret']
	return Customer


@frappe.whitelist()
def get_order_info(order_id):
	order = frappe.get_doc('Order', order_id)
	delivery_slot = []
	check_slot = frappe.db.get_all('Order Delivery Slot',
				 filters={'order': order_id}, 
				 fields=['order_date', 'from_time', 'to_time', 'product_category'])
	if check_slot:
		for deli_slot in check_slot:
			category = ''
			if deli_slot.product_category:
				category = frappe.get_value('Product Category', 
						   deli_slot.product_category, 'category_name')
			from_time = datetime.strptime(str(deli_slot.from_time), '%H:%M:%S').time()
			to_time = datetime.strptime(str(deli_slot.to_time), '%H:%M:%S').time()
			delivery_slot.append({
								  'delivery_date': deli_slot.order_date.strftime('%b %d, %Y'),
								  'from_time'    : from_time.strftime('%I:%M %p'),
								  'to_time'      : to_time.strftime('%I:%M %p'),
								  'category'     : category
								})
	feedback = frappe.db.get_all('Order Feedback',
				 filters={'order': order_id}, 
				 fields=['posted_on', 'ratings', 'comments'])
	return {"info":order,"messages":[],"delivery_slot":delivery_slot,'feedback':feedback[0] \
				if feedback else None}

@frappe.whitelist()
def insert_update_customer(**info):
	try:
		if info.get('cmd'):
			del info['cmd']
		if not info.get("name"):
			if frappe.db.get_all(info.get("doctype"),filters={"email":info.get("email")}):
				frappe.local.response.status = "Failed"
				frappe.local.response.message = "Email is already registered."
				return
			if frappe.db.get_all(info.get("doctype"),filters={"phone":info.get("phone")}):
				frappe.local.response.status = "Failed"
				frappe.local.response.message = "Phone Number is already registered."
				return
		if info.get('name'):
			doc = frappe.get_doc(info.get("doctype"),info.get('name'))
			doc.update(info)
			doc.save(ignore_permissions = True)
		else:
			doc = frappe.get_doc(info)
			doc.insert(ignore_permissions = True)
		frappe.local.response.status = "Success"
		frappe.local.response.data = doc
	except Exception:
		other_exception("Error in v2.customer.insert_cust_details")


def insert_update_br(info):
	doc = frappe.new_doc(info.get("doctype"))
	for key, value in info.items():
		if key!="doctype" and key!="business_identity_proof" and \
			key!="business_address_proof" and key!="business_documents":
			setattr(doc, key, value)
	if info.get("business_identity_proof"):
		for d in info.get("business_identity_proof"):
			doc.append("business_identity_proof",{
							"identity_proof":d.get("identity_proof"),
							"identity_proof_attachment":d.get("identity_proof_attachment")})
	if info.get("business_address_proof"):
		for d in (info.get("business_address_proof")):
			doc.append("business_address_proof",{
						"address_proof":d.get("address_proof"),
						"address_proof_attachment":d.get("address_proof_attachment")})
	if info.get("business_documents"):
		for d in (info.get("business_documents")):
			doc.append("business_documents",{
						"business_kycdocument":d.get("business_kycdocument"),
						"kyc_doc_attachment":d.get("kyc_doc_attachment")})		
	doc.save(ignore_permissions = True)
	return doc

@frappe.whitelist()
def insert_contact_enquiry(**info):
	result = frappe.get_doc({
		'doctype': 'Contact Enquiry',
		'full_name': info.get('username'),
		'email_id': info.get('mailid'),
		'phone_number': info.get('phonenumber'),
		'subject': info.get('subject'),
		'message': info.get('message'),
	}).insert(ignore_permissions=True)
	return result

@frappe.whitelist()
def cancel_order(**kwargs):
	try:
		frappe.log_error("kwargs", kwargs)
		customer_id = frappe.db.get_value("Order",kwargs.get("order_id"),"customer")
		customer = kwargs.get("customer") if kwargs.get("customer") else get_customer_from_token()
		frappe.log_error("Customer Details", [customer, customer_id])
		if customer and customer == customer_id:
			Orders = frappe.get_doc("Order", kwargs.get("order_id"))
			if Orders:
				if Orders.docstatus == 2:
					return {"Order": kwargs.get("order_id"),"message": "Already Order cancelled"}
				else:
					return validate_cancel_order(Orders,customer_id,**kwargs)
			else: 
				return {"status":"Failed",
						"message": "Order id Not Found"}
		else:
			return {"status":"Failed",
					"message": "Not valid customer."}
	except frappe.exceptions.DoesNotExistError:
		doesnotexist_exception()
	except frappe.exceptions.ValidationError:
		validation_exception()
	except frappe.exceptions.PermissionError:
		permission_exception()
	except frappe.exceptions.LinkExistsError:
		return {"order_id": kwargs.get("order_id"),
				"message": "Order and Vendor Order Cancel Successfully"}
	except Exception:
		other_exception("customer cancel_order")

def validate_cancel_order(Orders,customer_id,**kwargs):
	if Orders.docstatus == 1:
		from frappe.desk.form.linked_with import get_linked_docs, get_linked_doctypes
		linkinfo = get_linked_doctypes(Orders.doctype)
		frappe.log_error("linkinfo",linkinfo)
		docs = get_linked_docs(Orders.doctype, Orders.name, linkinfo)
		for key in docs:
			for item in docs[key]:
				if item.get("docstatus")==1:
					frappe.db.set_value(key,item.get("name"),"docstatus",2)
		Orders.docstatus = 2
		Orders.cancel_reason = kwargs.get("cancel_reason")
		Orders.status = "Cancelled"
		Orders.update(kwargs)
		Orders.save(ignore_permissions=True)
		OrderItem = DocType("Order Item")
		old_items = (
			frappe.qb.from_(OrderItem)
			.select(OrderItem.item, OrderItem.quantity, OrderItem.attribute_ids)
			.where(OrderItem.parent == kwargs.get("order_id"))
			.run(as_dict=True)
		)
		if Orders.paid_using_wallet>0:
			wallet = frappe.db.get_all("Wallet",filters={"user":Orders.customer})
			if wallet:
				wallet_doc = frappe.get_doc("Wallet", wallet[0].name)
				cur_wallet = flt(wallet_doc.current_wallet_amount)+(1*flt(Orders.paid_using_wallet))
				locked_in = flt(wallet_doc.locked_in_amount)
				total_wallet = flt(cur_wallet)+flt(locked_in)
				wallet_doc.current_wallet_amount=cur_wallet
				wallet_doc.locked_in_amount=locked_in
				wallet_doc.total_wallet_amount=total_wallet
				wallet_doc.save(ignore_permissions=True)
		frappe.db.commit()
		return {"status":"Success",
			"message": "Order Cancel Successfully"}

def generate_random_nos(n):
	from random import randint
	range_start = 10**(n-1)
	range_end = (10**n)-1
	return randint(range_start, range_end)

@frappe.whitelist(allow_guest=True)
def send_otp(mobile_no):
	from go1_commerce.go1_commerce.v2.common \
		import send_otp as send_mobile_otp
	return send_mobile_otp(mobile_no)

@frappe.whitelist(allow_guest=True)
def verify_otp(mobile_no,otp,guest_id=None):
	from go1_commerce.go1_commerce.v2.common \
		import validate_otp
	otp_resp =  validate_otp(mobile_no,otp,"Customer")
	if otp_resp.get("status")=="Success":
		if guest_id:
			move_cart_items(otp_resp.get("customer_id"), guest_id)
		return otp_resp
	else:
		return otp_resp

def move_cart_items(customer, guest_id):
	try:
		from go1_commerce.go1_commerce.v2.cart \
			import update_cart
		if not guest_id:
			guest = frappe.request.cookies.get('guest_customer')
		else:
			guest = guest_id
		if guest:
			guest_cart = frappe.db.get_all('Shopping Cart',filters={'customer': guest, 
											'cart_type': 'Shopping Cart'},fields=['name'])
			if guest_cart:
				update_cart('Shopping Cart', customer, guest, guest_cart)
			guest_cart2 = frappe.db.get_all('Shopping Cart', 
										filters={'customer': guest, 'cart_type': 'Wishlist'},
										fields=['name'])
			if guest_cart2:
				update_cart('Wishlist', customer, guest, guest_cart2)
			recently_viewed_products = frappe.get_all('Customer Viewed Product',
										fields=['product'], filters={'parent': guest_id}, 
										order_by='viewed_date desc')
			if recently_viewed_products:
				update_recently_viewed_products(guest_id, customer)
	except Exception:
		frappe.log_error(message = frappe.get_traceback(),title='v2.customer.move_cart_items')

@frappe.whitelist(allow_guest=True)
def update_recently_viewed_products(guest_id, customer_id):
	recently_viewed_products = frappe.get_all('Customer Viewed Product', 
										fields=['product', 'viewed_date', 'name'],
										filters={'parent': guest_id}, order_by='viewed_date desc')
	for x in recently_viewed_products:
		frappe.enqueue("go1_commerce.go1_commerce.api.delete_viewed_products",customer_id=customer_id, name=x.name, product=x.product)

@frappe.whitelist(allow_guest=True)
def delete_viewed_products(customer_id, name, product):
	check_already_viewed = frappe.get_all('Customer Viewed Product', filters={'parent': customer_id, 'product': product})
	if not check_already_viewed:
		customer_viewed_product = frappe.new_doc('Customer Viewed Product')
		customer_viewed_product.parent = customer_id
		customer_viewed_product.parenttype = 'Customers'
		customer_viewed_product.parentfield = 'viewed_products'
		customer_viewed_product.product = product
		customer_viewed_product.viewed_date = getdate(nowdate())
		customer_viewed_product.save(ignore_permissions=True)
		frappe.db.commit()
	else:
		check_already_viewed_update = check_already_viewed[0]
		customer_viewed_product = frappe.get_doc('Customer Viewed Product', check_already_viewed_update.name)
		customer_viewed_product.viewed_date = getdate(nowdate())
		customer_viewed_product.save(ignore_permissions=True)
		frappe.db.commit()
	remove_product = frappe.get_doc('Customer Viewed Product', name)
	remove_product.delete()
	frappe.db.commit()

def customer_login(phone):
	usr = frappe.db.get_all("Customers",
							filters={"phone":phone,"customer_status":"Approved"},
							fields=["email","name","full_name"])
	if usr:
		token = get_auth_token(usr[0].email)
		if token:
			has_role = frappe.db.get_all('Has Role',
							filters={'parent': usr[0].email, 'role': "Customer"})
			if not has_role:
				frappe.local.response.http_status_code = 500
				frappe.local.response.status = "Failed"
				frappe.local.response.message = "You dont have access."
				return
			return {'type':'Customer',
					'api_key': token['api_key'],
					'api_secret': token['api_secret'],
					'customer_id':usr[0].name,
					'customer_email':usr[0].email,
					'customer_name':usr[0].full_name,
					'status':"Success",
					"message":"OTP verfied successfully."}
	return {"status":"Failed"}

def customer_registration_login(phone):
	usr = frappe.db.get_value("Customer Registration",{"phone":phone})
	if usr:
		cus_reg = frappe.get_doc("Customer Registration",usr)
		if not cus_reg.uuid:
			import uuid
			cus_reg.uuid  = uuid.uuid4().hex
			cus_reg.save(ignore_permissions=True)
		return {'type':'Customer Registration',
				'data':cus_reg,
				'status':"Success",
				"message":"OTP verfied successfully."}
	else:
		import uuid
		cus_reg = frappe.new_doc("Customer Registration")
		cus_reg.phone = phone
		cus_reg.uuid  = uuid.uuid4().hex
		cus_reg.save(ignore_permissions=True)
		return {'type':'Customer Registration',
				'data':cus_reg,
				'status':"Success",
				"message":"OTP verfied successfully."}	

@frappe.whitelist(allow_guest=True)
def get_registration_details(customer_id):
	from go1_commerce.utils.utils import get_customer_reg_from_token
	reg_id = get_customer_reg_from_token()
	if reg_id == customer_id:
		return frappe.get_doc("Customer Registration",customer_id)
	return {"status":"Failed","message":"Authoriztion Failed."}

@frappe.whitelist(allow_guest=True)
@customer_reg_auth(method="POST")
def update_registration_details(**kwargs):
	try:
		from go1_commerce.utils.utils import get_customer_reg_from_token
		reg_id = get_customer_reg_from_token()
		if reg_id == kwargs.get("name"):
			reg_doc = frappe.get_doc("Customer Registration",kwargs.get("name"))
			if kwargs.get("address_map") is not None:
				del kwargs['address_map'] 
			if kwargs.get("business_address_map") is not None:
				del kwargs['business_address_map']
			reg_doc.update(kwargs)
			reg_doc.save(ignore_permissions=True)
			return {"status":"Success","data":reg_doc,"message":"Registration details updated successfully."}
		return {"status":"Failed","message":"Authoriztion Failed."}
	except frappe.exceptions.ValidationError as ve:
		return {"status":"Failed","message":str(ve) }
	except Exception:
		other_exception("customer update_registration_details")
		return {"status":"Failed","message":"Something went wrong."}

@frappe.whitelist()
def get_wallet_details(customer=None):
	try:
		if not customer:
			customer = get_customer_from_token()
		Wallet = DocType("Wallet")
		wallet_amount = (
			frappe.qb.from_(Wallet)
			.select("*")
			.where(Wallet.user == customer)
			.run(as_dict=True)
		)
		if wallet_amount:
			return wallet_amount
	except Exception:
		frappe.log_error(message = frappe.get_traceback(), title = 'Error in wallet_details')

@frappe.whitelist()
def update_device_id(device_id, customer=None):
	try:
		if not customer:
			customer = get_customer_from_token()
		if customer:
			from go1_commerce.go1_commerce.v2.common import update_device_id
			update_device_id('Customers',customer,device_id,'Customer')
			return {"status":"Success","message":"Device ID updated successfully."}
		return {"status":"Failed","message":"Not a valid customer"}
	except Exception:
		frappe.log_error(message = frappe.get_traceback(), title = 'Error in update_device_i')

@frappe.whitelist()
def insert_address(data):
	try:
		check = check_address(data)
		if check:
			return check
		response = json.loads(data)
		if response.get('customer'):
			filters = {'name': response.get('customer')}
		else:
			filters = {'user_id': frappe.session.user}
		customers = frappe.db.get_all('Customers', filters = filters, fields = ['*'])
		if response.get('is_default') == 1:
			CustomerAddress = DocType("Customer Address")
			existing_address = (
				frappe.qb.from_(CustomerAddress)
				.select("*")
				.where(CustomerAddress.parent == customers[0].name)
				.run(as_dict=True)
			)
			if existing_address:
				for address in existing_address:
					addr = frappe.get_doc('Customer Address', address.name)
					addr.is_default = 0
					addr.save()
		check_existing = frappe.db.get_all('Customer Address', 
										filters={	'parent': customers[0].name, 
													'address': response.get('addr1'), 
													'city': response.get('city'), 
													'state': response.get('state'), 
													'country': response.get('country')})
		if check_existing:
			return {'status': 'failed', 
					'message': _('You have already added this address')}
		if response.get('address_type'):
			res = validate_address(response.get('address_type'), customers[0].name)
			if res and res['status'] == 'failed':
				return res
		address = frappe.new_doc('Customer Address')
		address.first_name = (response.get('first_name') if response.get('first_name') else customers[0].first_name)
		address.last_name = (response.get('last_name') if response.get('last_name') else customers[0].last_name)
		set_address_details(address,customers,response)
		address.save()
		return address.as_dict()
	except Exception:
		frappe.log_error(message=frappe.get_traceback(), title='v2.customer.insert_address')

def set_address_details(address,customers,response):
	if address.first_name == 'Guest':
		address.first_name = customers[0].first_name
	if address.last_name == 'None':
		address.last_name = customers[0].last_name
	address.address = response.get('addr1')
	address.city = response.get('city')
	address.county = response.get('district')
	address.is_default = response.get('is_default')
	address.state = response.get('state')
	address.country = response.get('country')
	address.zipcode = response.get('pincode')
	if response.get('phone'):
		address.phone = response.get('phone')
	else:
		address.phone = customers[0].phone
	address.parenttype = 'Customers'
	address.parentfield = 'table_6'
	address.landmark = response.get('landmark')
	address.parent = customers[0].name
	if response.get('address_type'):
		address.address_type = response.get('address_type')
	if response.get('door_no'):
		address.door_no = response.get('door_no')
	if response.get('unit_number'):
		address.unit_number = response.get('unit_number')
	if response.get('latitude'):
		address.latitude = response.get('latitude')
	if response.get('longitude'):
		address.longitude = response.get('longitude')

@frappe.whitelist()
def delete_address(id, customer):
	try:
		addr = frappe.db.get_all('Customer Address',
								 filters={'parent': customer,
								 'name': id})
		if addr:
		
			CustomerAddress = DocType('Customer Address')
			query = (
				frappe.qb.from_(CustomerAddress)
				.delete()
				.where(CustomerAddress.name == addr[0].name)
			)
			query.run()
			frappe.db.commit()
			return 'Success'
	except Exception:
		frappe.log_error(message=frappe.get_traceback(), title='v2.customer.delete_address')

def validate_address(addr_type, customer, addrId=None):
	general_settings = frappe.get_single('Business Setting')
	if general_settings.restrict_address:
		filters = [['parent', '=', customer], ['address_type', '=', addr_type]]
		if addrId:
			filters.append(['name', '!=', addrId])
		address = frappe.db.get_all('Customer Address', filters=filters)
		if addr_type == 'Home' or addr_type == 'Work':
			if len(address) == 1:
				return {'status': 'failed', 
						'message': _('Only one {0} address can be added.').format(addr_type.lower())}
		if addr_type == 'Others':
			if len(address) >= int(general_settings.max_other_address):
				return {'status': 'failed', 
						'message': _('Only {0} address in other category can be added.').\
									format(general_settings.max_other_address)}
	return {'status': 'Success'}

def check_address(data):
	response = json.loads(data)
	address = frappe.db.get_all('Customer Address', fields=['*'], 
								   filters={'address': response.get('address'), 
											'city': response.get('city'),
											'state': response.get('state'),
											'country': response.get('country'), 
											'zipcode': response.get('zipcode'), 
											'parent': response.get('customer') })
	if address:
		return address[0]

@frappe.whitelist()
def update_address(data):
	try:
		response = json.loads(data)
		customers = frappe.db.get_all('Customers',
				filters={'name': response.get('parent')}, fields=['*'])
		if response.get('is_default') == 1:
			
			CustomerAddress = DocType('Customer Address')
			query = (
				frappe.qb.from_(CustomerAddress)
				.select("*")
				.where(CustomerAddress.parent == customers[0].name)
			)
			existing_adddress= query.run(as_dict=True)
			for address in existing_adddress:
				addr = frappe.get_doc('Customer Address', address.name)
				addr.is_default = 0
				addr.save(ignore_permissions=True)
		if response.get('address_type'):
			res = validate_address(response.get('address_type'), customers[0].name, response.get('name'))
			if res and res['status'] == 'failed':
				return res
		address = frappe.get_doc('Customer Address', response.get('name'))
		if response.get('first_name'):
			address.first_name = response.get('first_name')
		if response.get('last_name'):
			address.last_name = response.get('last_name')
		address.address = response.get('addr1')
		address.city = response.get('city')
		address.county = response.get('district')
		address.is_default = response.get('is_default')
		address.state = response.get('state')
		address.country = response.get('country')
		address.zipcode = response.get('pincode')
		address.phone = response.get('phone')
		address.landmark = response.get('landmark')
		if response.get('address_type'):
			address.address_type = response.get('address_type')
		if response.get('door_no'):
			address.door_no = response.get('door_no')
		if response.get('unit_number'):
			address.unit_number = response.get('unit_number')
		if response.get('latitude'):
			address.latitude = response.get('latitude')
		if response.get('longitude'):
			address.longitude = response.get('longitude')
		address.save(ignore_permissions=True)
		return address.as_dict()
	except Exception:
		frappe.log_error(message = frappe.get_traceback(), title = 'v2.customer.update_address')


@frappe.whitelist(allow_guest=True)
def insert_customers(data):
	try:
		if isinstance(data, string_types):
			data = json.loads(data)
		responsedata = data
		parent_customer = None
		regapproval = 0 
		if responsedata.get('reg_approval') and (responsedata.get('reg_approval') == 1 or responsedata.get('reg_approval') == "1"):
			regapproval = 1
		document = "Customers"
		exist_reg = None
		# if regapproval==1:
		# 	document = "Customer Registration"
		# 	exist_reg = frappe.db.get_value(document,{"phone": responsedata.get("phone"), "customer_status":("!=", "Rejected")})
		# 	if responsedata.get("email"):
		# 		if frappe.db.exists("Customer Registration", {"email": responsedata.get("email"), "customer_status":("!=", "Rejected")}):
		# 			return {'status':'failed','customer':"", 'msg': "Email already registered!"}
		# if regapproval==0:
		exist_reg = frappe.db.get_value(document,{"phone": responsedata.get("phone"), "customer_status":("!=", "Rejected")})
		if exist_reg:
			return {'status':'failed','customer':"", 'message': "Mobile Number already registered!"}
		if responsedata.get("email"):
			if frappe.db.exists("Customers", {"email": responsedata.get("email"), "customer_status":("!=", "Rejected")}):
				return {'status':'failed','customer':"", 'message': "Email already registered!"}
		
		if responsedata.get('name'):
			customer = frappe.get_doc(document,responsedata.get('name'))
		else:	
			customer = frappe.new_doc(document)
			
		customer.first_name = responsedata.get("first_name")
		customer.last_name = responsedata.get("last_name")
		order_settings = get_settings('Order Settings')
		customer.customer_status = "Approved" if order_settings.auto_customer_approval else "Waiting for Approval"
		if responsedata.get('phone'):
			customer.phone = responsedata.get("phone")
		customer.email = responsedata.get("email")
		customer.gender = responsedata.get("gender")
		if responsedata.get('random_pwd'):
			customer.set_new_password = frappe.generate_hash(length=8)
		else:
			customer.set_new_password = responsedata.get('pwd')
		if responsedata.get('address'):
			customer.table_6 = []			
			for item in responsedata.get('address'):
				customer.append('table_6', item)
		if responsedata.get('parent_customer'):
			customer.parent_doctype = 'Customers'
			customer.parent_level = responsedata.get('parent_customer')
		if exist_reg and regapproval==1:
			return {'status':'failed','customer':"", 'msg': "Customer already registered!"}
		else:
			customer.save(ignore_permissions=True)
		if regapproval==0:
			# created by sivaranjani-21 july 2020
			if responsedata.get('custom_role'):
				cur_cust = frappe.get_doc("Customers", customer.name)
				cur_cust.append("customer_role", {"role": responsedata.get('custom_role')})
				cur_cust.save(ignore_permissions=True)
			#end
			if responsedata.get('guest_id'):
				move_cart_items(customer.name, responsedata.get('guest_id'))
		return {'status':'success','customer':customer, 'msg':"","message":"Congratulations your account has been successfully created."}
	except Exception as e:
		frappe.db.rollback()	
		frappe.log_error(frappe.get_traceback(), "go1_commerce.go1_commerce.v2.customer.insert_customers")
		return {'status':'failed', 'msg':""}
