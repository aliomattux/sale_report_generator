from openerp.osv import osv, fields
from datetime import datetime
from openerp.tools.translate import _
from tempfile import TemporaryFile
import time
from base_file_protocole import FileCsvWriter


class SaleReportWizard(osv.osv_memory):
    _name = 'sale.report.wizard'
    _columns = {
	'date_from': fields.date('From Date', required=True),
	'date_to': fields.date('To Date', required=True),
	'report': fields.selection([('incoming', 'Accounts Receivable (Customer Payments)'),
				    ('outgoing', 'Accounts Payable (Vendor Payments)'),
				    ('top_items', 'Top Sold Items'),
				    ('customers', 'Top Customers'),
				    ('customers_brand', 'Customers by Brand'),
	], 'Report Type', required=True),
	'show_detail': fields.boolean('Show Transaction Details'),
	'format': fields.selection([('csv', 'Excel/CSV'),
				    ('iif', 'Quickbooks (iif)'),
	], 'Report Format', required=True),
	'record_limit': fields.integer('Record Limit'),
        'brand': fields.many2one('product.attribute.value', 'Brand',
                domain="[('attribute_code', '=', 'brand')]"),

    }


    def get_customer_brand_data(self, cr, uid, wizard, context=None):
	query = """
		SELECT DISTINCT partner.name AS "customer name", COALESCE(sale.order_email, partner.email) AS "customer email", partner.phone AS "customer phone"
		\nFROM sale_order sale
		\nJOIN sale_order_line line ON (sale.id = line.order_id)
		\nJOIN res_partner partner ON (partner.id = sale.partner_invoice_id)
		\nJOIN product_product product ON (line.product_id = product.id)
		\nJOIN product_template template ON (template.id = product.product_tmpl_id)
		\nWHERE sale.state != 'cancel'
		\nAND template.brand = %s
                \n AND sale.create_date AT TIME ZONE 'UTC' >= '%s' AND sale.create_date AT TIME ZONE 'UTC' <= '%s'
        """ % (wizard.brand.id, wizard.date_from, wizard.date_to)

	if wizard.record_limit:
	    query += "\nLIMIT %s" % wizard.record_limit

        cr.execute(query)

        return cr.dictfetchall()


    def get_top_customer_data(self, cr, uid, wizard, context=None):
        query = """
		SELECT partner.name as "customer name", COALESCE(sale.order_email, partner.email) as "customer email", partner.phone AS "customer phone", COUNT(sale.id) AS no_of_orders, SUM(sale.amount_total) AS lifetime_sales
		\nFROM sale_order sale
		\nJOIN res_partner partner ON (sale.partner_invoice_id = partner.id)
		\nWHERE sale.state != 'cancel'
		\n AND sale.create_date AT TIME ZONE 'UTC' >= '%s' AND sale.create_date AT TIME ZONE 'UTC' <= '%s'
	""" % (wizard.date_from, wizard.date_to)

	group_sql = """
		\nGROUP BY partner.name, sale.order_email, partner.email, partner.phone
		\nORDER BY SUM(sale.amount_total) DESC
	"""

        query += group_sql

        if wizard.record_limit:
            query += "\nLIMIT %s" % wizard.record_limit

        cr.execute(query)

        return cr.dictfetchall()


    def get_top_product_data(self, cr, uid, wizard, context=None):
        query = """
		SELECT product.default_code as sku, template.name, CAST(SUM(product_uom_qty) AS INT) as "number sold"
		\nFROM sale_order_line line
		\nJOIN sale_order sale ON (sale.id = line.order_id)
		\nJOIN product_product product ON (line.product_id = product.id)
		\nJOIN product_template template ON (template.id = product.product_tmpl_id)
		\nWHERE product.default_code NOT IN ('mage_shipping', 'STORECREDIT', 'Gift Wrap', 'giftcard')
		\nAND line.create_date AT TIME ZONE 'UTC' >= '%s' AND line.create_date AT TIME ZONE 'UTC' <= '%s'
	""" % (wizard.date_from, wizard.date_to)

	if wizard.brand:
	    query += "\nAND template.brand = '%s'" % wizard.brand.id


	group_sql = """
			\nGROUP BY product.default_code, template.name
			\nORDER BY SUM(product_uom_qty) DESC
	"""
	query += group_sql

        if wizard.record_limit:
            query += "\nLIMIT %s" % wizard.record_limit

	cr.execute(query)

	return cr.dictfetchall()


    def get_fieldnames(self, cr, uid, wizard, context=None):
	if wizard.report in ['incoming', 'outging']:
	    fieldnames = ['Metric', 'Credit', 'Debit', '1', '2']
	elif wizard.report == 'top_items':
	    fieldnames = ['sku', 'name', 'number sold', 'brand']
	elif wizard.report == 'customers':
	    fieldnames = ['customer name', 'customer email', 'customer phone', 'no_of_orders', 'lifetime_sales']
	elif wizard.report == 'customers_brand':
	    fieldnames = ['customer name', 'customer email', 'customer phone', 'brand']

	return fieldnames


    def generate_csv_file(self, cr, uid, fieldnames, wizard, context=None):
	if wizard.report in ['incoming', 'outgoing']:
	    writeheader = False
	else:
	    writeheader = True

	output_file = TemporaryFile('w+b')
        writer = FileCsvWriter(output_file, fieldnames, encoding="utf-8", writeheader=writeheader, delimiter=',', \
                            quotechar='"')

	return writer, output_file


    def prepare_and_send_report(self, cr, uid, ids, context=None):
	wizard = self.browse(cr, uid, ids[0])
	fieldnames = self.get_fieldnames(cr, uid, wizard)
	writer, output_file = self.generate_csv_file(cr, uid, fieldnames, wizard)
	if wizard.report in ['incoming', 'outgoing']:
	    return self.execute_financial_report(cr, uid, wizard, writer, output_file)
	else:
	    return self.execute_data_report(cr, uid, wizard, writer, output_file)


    def execute_data_report(self, cr, uid, wizard, writer, output_file, context=None):
	if wizard.report == 'top_items':
	    report_name = 'Top Items'
	    report_filename = 'top_items.csv'
	    data = self.get_top_product_data(cr, uid, wizard)

        elif wizard.report == 'customers':
            report_name = 'Customers'
            report_filename = 'customers.csv'
            data = self.get_top_customer_data(cr, uid, wizard)

        elif wizard.report == 'customers_brand':
            report_name = 'Customers by Brand'
            report_filename = 'customers_brand.csv'
            data = self.get_customer_brand_data(cr, uid, wizard)

	for row in data:
	    if wizard.brand:
		row['brand'] = wizard.brand.name

	    writer.writerow(row)

        return self.pool.get('pop.up.file').open_output_file(cr, uid, report_filename, output_file, \
                report_name, context=context)


    def execute_financial_report(self, cr, uid, wizard, writer, output_file, context=None):
	if wizard.report == 'incoming':
	    report_name = 'Customer Payments'
	    report_filename = 'customer_payments.csv'
#	    return self.execute_incoming_report(cr, uid)
	elif wizard.report == 'outgoing':
	    report_name = 'Vendor Payments'
	    report_filename = 'vendor_payments.csv'
#	    return self.execute_outgoing_report(cr, uid)

	writer.writerow({'Metric': 'Report Name', 'Credit': report_name})
	writer.writerow({'Metric': 'Date Run',
			'Credit': datetime.now().strftime('%m/%d/%Y %H:%M'),
			'1': 'Accounting Period',
			'2': wizard.date_from + ' - ' + wizard.date_to
	})
	writer.writerow({})
	writer.writerow({})
	writer.writerow({'Metric': 'Metric', 'Credit': 'Credit', 'Debit': 'Debit'})
	metrics = [
		{'Metric': 'Gross Sales', 'Credit': '', 'Debit': ''},
		{'Metric': 'Gross Sales - Non Taxable', 'Credit': '', 'Debit': ''},
		{'Metric': 'Store Credits', 'Credit': '', 'Debit': ''},
		{'Metric': 'Returns', 'Credit': '', 'Debit': ''},
		{'Metric': 'Gift Card', 'Credit': '', 'Debit': ''},
		{'Metric': 'Shipping Charges', 'Credit': '', 'Debit': ''},
		{'Metric': 'Amex', 'Credit': '', 'Debit': ''},
		{'Metric': 'MC/Visa/Discover', 'Credit': '', 'Debit': ''},
		{'Metric': 'Discounts', 'Credit': '', 'Debit': ''},
		{'Metric': 'Restocking Fee', 'Credit': '', 'Debit': ''},
		{'Metric': 'Gift Wrap', 'Credit': '', 'Debit': ''},
		{'Metric': 'Exchanges', 'Credit': '', 'Debit': ''},
		{'Metric': 'Tax', 'Credit': '', 'Debit': ''},


	]
	for metric in metrics:
	    writer.writerow(metric)

        return self.pool.get('pop.up.file').open_output_file(cr, uid, report_filename, output_file, \
		report_name, context=context)


    def get_paid_vouchers(self, cr, uid, from_date, to_date, type):
        query = "SELECT id AS voucher_id, invoice AS invoice_id" \
		"\nFROM account_voucher" \
		"\n WHERE date >= %s AND date <=" % (from_date, to_date)

	cr.execute_query
	voucher_data = cr.dictfetchall()
	for voucher in voucher_data:
	    print voucher

	return True
