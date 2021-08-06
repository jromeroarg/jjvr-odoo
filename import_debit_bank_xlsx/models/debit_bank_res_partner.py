# -*- coding: utf-8 -*-

from odoo import api, fields, models
from datetime import datetime

class DebitBankResPartner(models.Model):
    _inherit = 'res.partner'

    debit_bank_ids = fields.One2many(
        comodel_name='debit.bank',
        string="Debito Bancario",
        compute="_compute_statement_vat_lines"
    )

    @api.depends('debit_bank_ids')
    def _compute_statement_vat_lines(self):
        res_obj = self.env['ir.model.data'].search([('model', '=', 'res.partner'),('res_id','=',self.id)])
        for rec in self:
            rec.debit_bank_ids = self.env['debit.bank'].search([('partida','=',res_obj.name),('status','=','Aprobado')])

