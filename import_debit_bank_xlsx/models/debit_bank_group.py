# -*- coding: utf-8 -*-

from odoo import api, fields, models
from datetime import datetime

class DebitBankGroup(models.Model):

    _name = "debit.bank.group"
    _description = "Debit Bank Group"
    _inherit = ['mail.thread']
    _order = 'date_from desc'
    
    periodo=fields.Char(String="Periodo",required=True)

    date_from = fields.Date(
        string='Fecha de Inicio',
        required=True,
    )
    date_to = fields.Date(
        string='Fecha de Fin',
        required=True,
    )
    debit_bank_ids = fields.One2many(
        comodel_name='debit.bank',
        string="Debito Bancario",
        compute="_compute_statement_vat_lines"
    )
    journal_id = fields.Many2one(
        comodel_name='account.journal',
        relation='debit_bank_group_account_journal_rel',
        string="Diario",
        required=True,
        domain=['|',('type','=','cash'),('type','=','bank')]
    )
    activo = fields.Boolean(string="Activo",default=True)

    @api.depends('debit_bank_ids', 'date_from', 'date_to')
    def _compute_statement_vat_lines(self):
        for rec in self:
            rec.debit_bank_ids = self.env['debit.bank'].search([
                ('fh_vencimiento', '>=', rec.date_from),
                ('fh_vencimiento', '<=', rec.date_to),
            ])

    @api.depends('debit_bank_ids', 'date_from', 'date_to', 'journal_id')
    def post_receipt(self):
        is_okey = True
        for rec in self.debit_bank_ids:
            # Debitos que dan error, 
            # se deben marcar, como no aplicados
            try:
                if((rec.status == 'Aprobado') and (rec.activo is True)):
                    debit_bank_obj = self.env['debit.bank'].search([('id', '=', rec.id)])
                    debit_bank_obj.generate_receipt(self.journal_id)
                elif (rec.status == 'Rechazado'):
                    rec.activo = False # Debito a inactivo, cuando esta rechazado
            except:
                rec.activo = True
                is_okey = False
        # debitos completos procesados, pasan a inactivos
        self.activo = not(is_okey)

