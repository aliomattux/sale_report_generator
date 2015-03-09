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
	], 'Report Type', required=True),
	'show_detail': fields.boolean('Show Transaction Details'),
	'format': fields.selection([('csv', 'Excel/CSV'),
				    ('iif', 'Quickbooks (iif)'),
	], 'Report Format', required=True),

    }


    def execute_report(self, cr, uid, ids, context=None):
	output_file = TemporaryFile('w+b')
	fieldnames = ['Metric', 'Credit', 'Debit', '1', '2']
	wizard = self.browse(cr, uid, ids[0])
	if wizard.report == 'incoming':
	    report_name = 'Customer Payments'
	    report_filename = 'customer_payments.csv'
#	    return self.execute_incoming_report(cr, uid)
	elif wizard.report == 'outgoing':
	    report_name = 'Vendor Payments'
	    report_filename = 'vendor_payments.csv'
#	    return self.execute_outgoing_report(cr, uid)

        writer = FileCsvWriter(output_file, fieldnames, encoding="utf-8", writeheader=False, delimiter=',', \
                            quotechar='"')

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
