# -*- coding: utf-8 -*-
# from odoo import http


# class ImportDebitBankXlsx(http.Controller):
#     @http.route('/import_debit_bank_xlsx/import_debit_bank_xlsx/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/import_debit_bank_xlsx/import_debit_bank_xlsx/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('import_debit_bank_xlsx.listing', {
#             'root': '/import_debit_bank_xlsx/import_debit_bank_xlsx',
#             'objects': http.request.env['import_debit_bank_xlsx.import_debit_bank_xlsx'].search([]),
#         })

#     @http.route('/import_debit_bank_xlsx/import_debit_bank_xlsx/objects/<model("import_debit_bank_xlsx.import_debit_bank_xlsx"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('import_debit_bank_xlsx.object', {
#             'object': obj
#         })
