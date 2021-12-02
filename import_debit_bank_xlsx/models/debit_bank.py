# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, Warning


class DebitBank(models.Model):
    _name = 'debit.bank'
    _description = 'Debit Bank'

    status = fields.Selection(string="Status",required=True,
        selection=[
                ('Aprobado','Aprobado'),
                ('Rechazado','Rechazado')])
    partida = fields.Char(string="Partida",required=True)
    importe = fields.Float(string="Importe",required=True)
    fh_vencimiento = fields.Date(string="Fecha Vencimiento",required=True)
    rechazo = fields.Char(string="Rechazo")
    motivo = fields.Text(string="Motivo")
    activo = fields.Boolean(string="Activo",default=True)
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string="Cliente",
        compute="_compute_res_partner_id"
    )

    @api.depends('partner_id','partida')
    def _compute_res_partner_id(self):
        for reg in self:
            partida_id = reg.partida.split('.')[-1]
            reg.partner_id = self.env['ir.model.data'].search([('model', '=', 'res.partner'),('name','=',partida_id)]).res_id

    @api.depends('status', 'partida', 'importe', 'fh_vencimiento', 'rechazo', 'motivo')
    def generate_receipt(self, journal_id):
        res_obj = self.env['ir.model.data'].search([('model', '=', 'res.partner'),('name','=',self.partida.split('.')[-1])])
        company_id = self.env.company.id
        currency_id = self.env.ref('base.main_company').currency_id
        payment_method = self.env['account.payment.method'].search([('payment_type', '=', 'inbound'),('code', '=', 'manual')])

        payment_id={}
        payment_id['payment_type']='inbound'
        payment_id['currency_id']=currency_id.id
        payment_id['partner_id']=res_obj.res_id
        payment_id['partner_type']='customer'
        payment_id['company_id']=company_id
        payment_id['journal_id']=journal_id.id
        payment_id['payment_method_id']=payment_method.id
        payment_id['amount']=self.importe
        payment_id['payment_date']=self.fh_vencimiento
        
        # Esto nos ubica en el contexto create_from_statement
        # Nos permite cear la account.payment
        self.env.context = dict(self.env.context)
        self.env.context.update({'create_from_expense': True,})

        payment = self.env['account.payment'].create(payment_id)


        payment.payment_group_id.action_draft()
        
        payment.payment_group_id.add_all()

        self.env.context.update({'create_from_expense': False,})
        self.env.context.update({'create_from_statement': True,})
        payment.payment_group_id.post()

        # Posteriormente al procesado, debemos convertir el debit bank a inactivo.
        self.activo = False
        