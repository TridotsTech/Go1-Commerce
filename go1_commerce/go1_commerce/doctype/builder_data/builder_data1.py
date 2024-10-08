# Copyright (c) 2024, Tridotstech PVT LTD and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.query_builder import Field,DocType

try:
	catalog_settings = get_settings('Catalog Settings')
	no_of_records_per_page = catalog_settings.no_of_records_per_page
except Exception as e:
	catalog_settings = None
	no_of_records_per_page = 10
	
class BuilderData(Document):
	def get_category_products(self,category=None, sort_by=None, page_no=1,
							 page_size=no_of_records_per_page,
							brands=None, rating=None,min_price=None, 
							max_price=None,attributes=None,
							productsid=None,customer=None,route=None):
		frappe.log_error("check_category",category)
		frappe.log_error("brands",brands)
		frappe.log_error("attributes",attributes)
		from go1_commerce.go1_commerce.v2.product import get_category_products as _get_category_products
		return _get_category_products(category=category, 
							sort_by=sort_by, 
							page_no=page_no,
							page_size=page_size,
							brands=brands, 
							rating=rating,
							min_price=min_price, 
							max_price=max_price,
							attributes=attributes,
							customer=customer,
							route=route)
	def get_product_details(self,route):
		from go1_commerce.go1_commerce.v2.product import get_product_details as _get_product_details
		return _get_product_details(route=route)
	def get_category_filters(self,route):
		from go1_commerce.go1_commerce.v2.category import get_category_filters as _get_category_filters
		return _get_category_filters(route=route)
	def get_attributes_data(self,options):
		options_data = options.split(",")
		options_filter = ""
		if options_data:
			options_filter = ','.join(['"' + x + '"' for x in options_data if x])
		
		ProductAttributeOption = DocType('Product Attribute Option')
		ProductAttribute = DocType('Product Attribute')

		query = (
			frappe.qb.from_(ProductAttributeOption)
			.inner_join(ProductAttribute)
			.on(ProductAttributeOption.attribute == ProductAttribute.name)
			.select(
				(ProductAttribute.attribute_name.concat(" : ")).as_("attribute_name"),
				ProductAttributeOption.option_value,
				ProductAttributeOption.unique_name
			)
			.where(ProductAttributeOption.unique_name.isin(options_filter))
		)

		selected_options_data = query.run(as_dict=True)
		return selected_options_data
