import frappe

@frappe.whitelist()
def update_global_script(doc,method):
    global_script = frappe.get_value("Builder Settings","Builder Settings","custom_server_script")
    if global_script:
        if doc.page_data_script:
            if "\n# Global Script\n" not in doc.page_data_script:
                doc.db_set('page_data_script',"\n# Global Script\n"+ global_script + "\n# Global Script\n\n"+ doc.page_data_script)
        else:
            doc.db_set('page_data_script',"\n# Global Script\n"+global_script + "\n# Global Script\n\n")
    frappe.db.commit()

@frappe.whitelist(allow_guest=True)
def get_mini_cart_html(cart_type,customer):
	from go1_commerce.go1_commerce.v2.cart import get_customer_cart
	if cart_type=="Shopping Cart":
		cart_obj = get_customer_cart("Shopping Cart",customer)
		if cart_obj.get("items"):
			currency = frappe.db.get_single_value("Catalog Settings","default_currency")
			currency_symbol = frappe.db.get_value("Currency",currency,"symbol")
			total_amount = 0
			for c in cart_obj.get("items"):
				c.formatted_price = frappe.utils.fmt_money(c["price"],currency=currency_symbol)
				total_amount = c["total"] + total_amount
			formatted_total = frappe.utils.fmt_money(total_amount,currency=currency_symbol)
			frappe.log_error("updated_Cart",cart_obj.get("items"))
			cart_html = frappe.render_template('templates/mini_shopping_cart.html',
											{"cart_items" :cart_obj.get("items")})
			return {"status":"Success","cart_html":cart_html,"total_amount":formatted_total}
		else:
			return {"status":"Failed"}
	else:
		cart_obj = get_customer_cart("Wishlist",customer)
		if cart_obj.get("items"):
			currency = frappe.db.get_single_value("Catalog Settings","default_currency")
			currency_symbol = frappe.db.get_value("Currency",currency,"symbol")
			total_amount = 0
			for c in cart_obj.get("items"):
				c.formatted_price = frappe.utils.fmt_money(c["price"],currency=currency_symbol)
			cart_html = frappe.render_template('templates/mini_wishlist.html',
											{"cart_items" :cart_obj.get("items")})
			return {"status":"Success","cart_html":cart_html}
		else:
			return {"status":"Failed"}

@frappe.whitelist(allow_guest=True)
def get_search_data(search_txt,page_no=1,page_len=15):
	from frappe.query_builder import DocType, Field, Order
	from go1_commerce.go1_commerce.v2.product import get_search_products
	ProductCategory = DocType('Product Category')
	params = {"search_text":search_txt,"page_no":page_no,"page_len":page_len}
	product_results = get_search_products(params)
	cat_query  = (
				frappe.qb.from_(ProductCategory)
				.select(ProductCategory.category_name,ProductCategory.name,ProductCategory.route) 
				.where((ProductCategory.is_active == 1) &
					(ProductCategory.category_name.like(f"%{search_txt}%"))
					
				)
			)
	category_results = cat_query.run(as_dict=True)
	return {"product_results":product_results,"category_results":category_results}