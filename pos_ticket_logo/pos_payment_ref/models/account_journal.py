# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    pos_payment_ref = fields.Boolean('POS Payment Ref', default=False)
    pos_payment_type = fields.Selection(selection=[('cupon_y_lote','Cupon y Lote'),('referencia_de_pago','Referencia de Pago')], default='referencia_de_pago', required=True)