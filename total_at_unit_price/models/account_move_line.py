# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"
    
    price_total = fields.Monetary(readonly=False)
    price_unit = fields.Float(digits=(12,7))

    @api.onchange('price_total')
    def _onchange_price_total(self):
        for rec in self:
            rec.price_unit = rec.calcule_subtotal()/rec.quantity if (rec.price_total > 0) else 0

    def get_percent_tax(self):
        percent_tax = 0
        for tax in self.tax_ids:
            percent_tax += tax.amount
        return percent_tax
    
    def calcule_subtotal(self):
        return (1/((1 + (self.get_percent_tax()/100))/self.price_total))