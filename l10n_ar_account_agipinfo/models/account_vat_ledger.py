##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, fields, api, exceptions, _
# from odoo.exceptions import ValidationError
from odoo.exceptions import UserError
from ast import literal_eval
from datetime import datetime, date
import base64
import logging
import re
_logger = logging.getLogger(__name__)


class AccountVatLedger(models.Model):
    _inherit = "account.vat.ledger"

    REGAGIP_CV_CBTE = fields.Text(
        'REGAGIP_CV_CBTE',
        readonly=True,
    )
    agip_vouchers_file = fields.Binary(
        compute='_compute_agip_files',
        readonly=True
    )
    agip_vouchers_filename = fields.Char(
        compute='_compute_agip_files',
    )

    REGAGIP_NC_CV_CBTE = fields.Text(
        'REGAGIP_NC_CV_CBTE',
        readonly=True,
    )
    agip_nc_vouchers_file = fields.Binary(
        compute='_compute_agip_nc_files',
        readonly=True
    )
    agip_nc_vouchers_filename = fields.Char(
        compute='_compute_agip_nc_files',
    )

    account_tax_per_id = fields.Many2one(
        comodel_name='account.tax',
        relation='account_vat_ledger_account_tax_per_rel',
        string="Impuesto Percepcion",
        domain=[('type_tax_use','=','sale')]
    )
    
    account_tax_ret_id = fields.Many2one(
        comodel_name='account.tax',
        relation='account_vat_ledger_account_tax_ret_rel',
        string="Impuesto Retencion",
        domain=[('type_tax_use','=','supplier')]
    )
    account_move_line_ids = fields.Many2many(
        comodel_name='account.move.line',
        relation='account_move_line_ids_rel',
        string="Account Move",
        compute='_compute_move_line'
    )


    def format_amount(self, amount, padding=15, decimals=2, invoice=False):
        # get amounts on correct sign despite conifiguration on taxes and tax
        # codes
        # TODO
        # remove this and perhups invoice argument (we always send invoice)
        # for invoice refund we dont change sign (we do this before)
        # if invoice:
        #     amount = abs(amount)
        #     if invoice.type in ['in_refund', 'out_refund']:
        #         amount = -1.0 * amount
        # Al final volvimos a agregar esto, lo necesitabamos por ej si se pasa
        # base negativa de no gravado
        # si se usa alguno de estos tipos de doc para rectificativa hay que pasarlos restando
        # seguramente para algunos otros tambien pero realmente no se usan y el digital tiende a depreciarse
        # y el uso de internal_type a cambiar
        if invoice and invoice.document_type_id.code in ['39', '40', '41', '66', '99'] \
           and invoice.type in ['in_refund', 'out_refund']:
            amount = -amount

        if amount < 0:
            template = "-{:0>%dd}" % (padding - 1)
        else:
            template = "{:0>%dd}" % (padding)
        return template.format(
            int(round(abs(amount) * 10**decimals, decimals)))

    def _compute_agip_files(self):
        self.ensure_one()
        # segun vimos aca la afip espera "ISO-8859-1" en vez de utf-8
        # http://www.planillasutiles.com.ar/2015/08/
        # como-descargar-los-archivos-de.html
        if self.REGAGIP_CV_CBTE:
            self.agip_vouchers_filename = _('AGIP_%s_%s.txt') % (
                self.type,
                self.date_to,
                # self.period_id.name
            )
            self.agip_vouchers_file = base64.encodestring(
                self.REGAGIP_CV_CBTE.encode('utf8'))
        else:
            self.agip_vouchers_file = None 
            self.agip_vouchers_filename = None

    def _compute_agip_nc_files(self):
        self.ensure_one()
        # segun vimos aca la afip espera "ISO-8859-1" en vez de utf-8
        # http://www.planillasutiles.com.ar/2015/08/
        # como-descargar-los-archivos-de.html
        if self.REGAGIP_NC_CV_CBTE:
            self.agip_nc_vouchers_filename = _('AGIP_NC_%s_%s.txt') % (
                self.type,
                self.date_to,
                # self.period_id.name
            )
            self.agip_nc_vouchers_file = base64.encodestring(
                self.REGAGIP_NC_CV_CBTE.encode('utf8'))
        else:
            self.agip_nc_vouchers_file = None 
            self.agip_nc_vouchers_filename = None

    @api.multi
    @api.depends('journal_ids','date_from', 'date_to')
    def _compute_move_line(self):
        for rec in self:
            account_move_lines_domain = [
                '|',('tax_line_id','=', rec.account_tax_per_id.id),
                ('tax_line_id','=', rec.account_tax_ret_id.id),
                ('company_id', '=', rec.company_id.id),
                ('date', '>=', rec.date_from),
                ('date', '<=', rec.date_to),
            ]
            account_move_lines = rec.env['account.move.line'].search(
                account_move_lines_domain,
                order='date asc, id asc'
            )
            rec.account_move_line_ids = account_move_lines

    def compute_agip_data(self):
        # sacamos todas las lineas y las juntamos
        # raise Warning("Valor de account_tax_ret_id:"+str(self.account_tax_per_id.id))
        # raise Warning("Cantidad de registros:"+str(len(self.account_move_line_ids)))
        lines = []
        self.ensure_one()
        for account_move_line in self.account_move_line_ids:
            # si es una nota de cr??dito se omite el registro, ya que tiene otro formato el txt
            # raise Warning("Cantidad de registros:"+invoice.document_type_id.internal_type)
            if account_move_line.document_type_id.internal_type == 'credit_note':
                continue
            mvt_per = None
            vat_amount = 0
            cantidad = 0
            if account_move_line.invoice_id:
                if account_move_line.invoice_id.currency_id.id == account_move_line.company_id.currency_id.id:
                    currency_rate = 1
                else:
                    currency_rate = account_move_line.invoice_id.currency_rate
                
                # # Inicio - Default
                # for mvt in invoice.tax_line_ids:
                #     if mvt.tax_id.id == self.account_tax_per_id.id:
                #         mvt_per = mvt
                #     if (mvt.tax_id.tax_group_id.type == 'tax') and (mvt.tax_id.tax_group_id.afip_code > 0):
                #         vat_amount += mvt.amount
                # # Fin - Default
                for mvt in account_move_line.invoice_id.tax_line_ids:
                    if mvt.tax_id.id == self.account_tax_per_id.id:
                        mvt_per = mvt
                    if (mvt.tax_id.tax_group_id.type == 'tax') and (mvt.tax_id.tax_group_id.afip_code > 0):
                        vat_amount += mvt.amount

                # si el comprobante no tiene la percpci??n buscada se omite el registro
                if not mvt_per:                 # si no est?? el impuesto buscado 
                    continue
                elif mvt_per.amount < 0.01:     # si est?? el impuesto pero con valor = 0
                    continue

                #Inicio del registro
                v = ''

                # Campo 1 - Tipo de Operaci??n
                # 1: Retenci??n
                # 2: Percepci??n
                v = '2'

                # Campo 2 - C??digo de Norma
                v+= '029'

                # Campo 3 - Fecha de retenci??n/percepci??n - Formato: dd/mm/aaaa
                # v+= invoice.date_invoice.strftime("%d/%m/%Y")
                aux1=account_move_line.invoice_id.date_invoice
                aux1=datetime.strptime(aux1, '%Y-%m-%d')
                v+= aux1.strftime("%d/%m/%Y")

                # Campo 4 - Tipo de comprobante origen de la retenci??n
                # Si Tipo de Operaci??n =1 : 
                # 01 . Factura
                # 02 . Nota de D??bito
                # 03 . Orden de Pago
                # 04 . Boleta de Dep??sito
                # 05 . Liquidaci??n de pago
                # 06 . Certificado de obra
                # 07 . Recibo
                # 08 . Cont de Loc de Servic.
                # 09 . Otro ComprobanteTipo Comprobante 
                # Si Tipo de Operaci??n =2: 
                # 01 . Factura
                # 09 . Otro Comprobante
                v+= '01'

                # Campo 5 - Letra del Comprobante
                # Operaci??n Retenciones
                # Si Agente=R.I y Suj.Ret = R.I : Letra= A,M,B
                # Si Agente=R.I y Suj.Ret = Exento : Letra= C
                # Si Agente=R.I y Suj.Ret = Monot. : Letra= C
                # Si Agente=Exento y Suj.Ret=R.I : Letra= B
                # Si Agente=Exento y Suj.Ret=Exento : Letra= C
                # Si Agente=Exento y Suj.Ret=Monot. : Letra= C
                # Operaci??n Percepci??n
                # Si Agente=R.I y Suj.Ret = R.I : Letra= A,M,B
                # Si Agente=R.I y Suj.Ret = Exento : Letra= B
                # Si Agente=R.I y Suj.Ret = Monot. : Letra= B
                # Si Agente=R.I y Suj.Ret = No Cat. : Letra= B
                # Si Agente=Exento y Suj.Ret=R.I : Letra=C
                # Si Agente=Exento y Suj.Ret=Exento : Letra= C
                # Si Agente=Exento y Suj.Ret=Monot. : Letra= C
                # Si Agente=Exento y Suj.Ret=No Cat. : Letra=C
                # Si Tipo Comprobante = (01,06,07): A,B,C,M 
                # sino 1 d??gito blanco
                # jjvr - As?? estaba en el original 
                # if invoice.partner_id.afip_responsability_type_id.code == '4':
                #     v+= 'C'
                # else:
                #     if invoice.document_type_id.code == '1':
                #         v+= 'A'
                #     elif invoice.document_type_id.code == '6':
                #         v+= 'B'
                # jjvr - Se decide tomar la letra del documento de AFIP para percepcion
                inv_letter = account_move_line.document_type_id.document_letter_id.name
                v+= inv_letter

                # Campo 6
                inv_number = account_move_line.invoice_id.document_number.replace('-','0')
                v+= inv_number.zfill(16)

                # Campo 7 - Fecha del comprobante - Formato: dd/mm/aaaa
                aux1=account_move_line.invoice_id.date_invoice
                aux1=datetime.strptime(aux1, '%Y-%m-%d')
                v+= aux1.strftime("%d/%m/%Y")

                # Campo 8 - Monto del comprobante total con impuestos incluidos
                # Decimales: 2
                # M??ximo: 9999999999999,99
                total_amount = account_move_line.invoice_id.amount_total*currency_rate
                v+= str('%.2f'%round(total_amount,2)).replace('.',',').zfill(16)

                # Campo 9 - Nro de certificado propio
                # Si Tipo de Operaci??n =1 se carga el Nro de certificado o blancos
                # Si Tipo de Operaci??n = 2 se completa con blancos.
                v+= ' ' * 16

                # Campo 10 - Tipo de documento del Retenido
                # 3: CUIT
                # 2: CUIL
                # 1: CDI
                m_categ_id_code = account_move_line.partner_id.main_id_category_id.code 
                if m_categ_id_code == "CUIT":
                    tip_doc_ret='3'
                elif m_categ_id_code == "CUIL":
                    tip_doc_ret='2'
                elif m_categ_id_code == "CDI":
                    tip_doc_ret='2'
                else:
                    tip_doc_ret=''
                v+= tip_doc_ret
                
                # Campo 11 - Nro de documento del Retenido
                # Mayor a 0(cero)
                # M??ximo: 99999999999            
                v+= account_move_line.partner_id.main_id_number.replace('-','').zfill(11) 

                # Campo 12 - Situaci??n IB del Retenido
                # 1: Local 
                # 2: Convenio Multilateral
                # 4: No inscripto 
                # 5: Reg.Simplificado
                # Si Tipo de Documento=3: Situaci??n IB del Retenido=(1,2,4,5)
                # Si Tipo de Documento=(1,2): Situaci??n IB del Retenido=4
                # p_gross_income_type=invoice.partner_id.gross_income_type
                # if tip_doc_ret == '3':
                #     if p_gross_income_type == 'local':
                #         sit_ib_ret='1'
                #     elif p_gross_income_type == 'multilateral':
                #         sit_ib_ret='2'
                #     elif p_gross_income_type == 'no_liquida':
                #         sit_ib_ret='4'
                #     else:
                #         sit_ib_ret= '5'
                # else:
                #     sit_ib_ret='4'
                sit_ib_ret='5'
                v+= sit_ib_ret
                    
                # Campo 13 - Nro Inscripci??n IB del Retenido
                # Si Situaci??n IB del Retenido=4 : 00000000000
                # Se validar?? digito verificador.
                # 1.Local: 8 dig??tos N??mero + 2 d??gitos Verificador
                # 2. Conv.Multilateral: 3 d??gitos Jurisdicci??n + 6 d??gitos N??mero + 1 D??gito Verificador
                # 5. Reg.Simplificado: 2 d??gitos + 8 d??gitos + 1 d??gito verificador
                # if sit_ib_ret == '4':
                #     nro_inscr_ret='00000000000'
                # elif not invoice.partner_id.gross_income_number:
                #     nro_inscr_ret=invoice.partner_id.main_id_number.replace('-','').zfill(11)
                # else:
                #     nro_inscr_ret=str(invoice.partner_id.gross_income_number).replace('-','').zfill(11)                
                nro_inscr_ret=account_move_line.partner_id.main_id_number.replace('-','').zfill(11)
                v+= nro_inscr_ret

                # Campo 14 - Situaci??n frente al IVA del Retenido
                # 1 - Responsable Inscripto
                # 3 - Exento
                # 4 - Monotributo
                sit_iva_ret=''
                if account_move_line.partner_id.afip_responsability_type_id.code == '1':
                    sit_iva_ret= '1'
                elif account_move_line.partner_id.afip_responsability_type_id.code == '4':
                    sit_iva_ret= '3'
                else:
                    sit_iva_ret= '4'
                v+=sit_iva_ret

                # Campo 15 - Raz??n Social del Retenido
                lastname = account_move_line.partner_id.name[:30]
                lastname = lastname.ljust(30).replace(' ','_')
                v+= lastname

                # Calculo adicionales:
                # De acuerdo a la alicuota, base y monto de la percepcion
                # se toma como el monto de la percepci??n declarado en la contabilidad
                amount = round(mvt_per.amount * currency_rate,2)
                alicuota = round((mvt_per.amount / mvt_per.base * 100),2)
                base = round((amount / alicuota * 100) ,2)
                vat_amount = round(vat_amount * currency_rate,2)
                imp_otr_vat = total_amount - vat_amount - base

                # Campo 16 - Importe otros conceptos
                # Decimales: 2
                # M??nimo: 0
                # M??ximo: 9999999999999,99
                # Importe Total del comprobante menos los conceptos de IVA
                v+= str('%.2f'%imp_otr_vat).replace('.',',').zfill(16)

                # Campo 17 - Importe IVA
                # Decimales: 2
                # M??nimo: 0
                # M??ximo: 9999999999999,99
                # Solo completar si Letra del Comprobante = (A,M)
                inv_letter = account_move_line.document_type_id.document_letter_id.name
                if (inv_letter == 'A') or (inv_letter == 'M'):
                    v+= str('%.2f'%vat_amount).replace('.',',').zfill(16)
                else:
                    v+= '0000000000000,00'

                # Campo 18 - Monto Sujeto a Retenci??n/ Percepci??n
                # Decimales: 2
                # M??nimo: 0
                # M??ximo: 9999999999999,99
                # Monto Sujeto a Retenci??n/ Percepci??n= (Monto del comprobante - Importe Iva - Importe otros conceptos)
                #base = mvt_per.base * currency_rate
                v+= str('%.2f'%base).replace('.',',').zfill(16)

                # Campo 19 -Al??cuota
                # Decimales: 2
                # M??nimo: 0
                # M??ximo: 99,99
                # Seg??n el Tipo de Operaci??n,C??digo de Norma y Tipo de Agente
                #alicuota = (mvt_per.amount / mvt_per.base * 100)
                v+= str('%.2f'%alicuota).replace('.',',').zfill(5)

                # Campo 20 - Retenci??n/Percepci??n Practicada
                # Decimales: 2
                # M??nimo: 0
                # M??ximo: 9999999999999,99
                # Retenci??n/Percepci??n Practicada= Monto Sujeto a Retenci??n/ Percepci??n * Al??cuota /100
                #amount = '%.2f'%round(mvt_per.amount  * currency_rate,2)
                v+= str('%.2f'%amount).replace('.',',').zfill(16)

                # Campo 21 - Monto Total Retenido/Percibido
                # Igual a Retenci??n/Percepci??n Practicada
                v+= str('%.2f'%amount).replace('.',',').zfill(16)

                # Campo 22
                v+= ' '*11

                lines.append(v)
            else:
                if account_move_line.payment_id.currency_id.id == account_move_line.company_id.currency_id.id:
                    currency_rate = 1
                else:
                    currency_rate = account_move_line.payment_id.currency_id.rate

                amount_ret=account_move_line.payment_id.amount
                base_amount_ret=account_move_line.payment_id.withholding_base_amount
                invoice_amount_ret=account_move_line.payment_id.withholdable_invoiced_amount
                vat_amount = 0

                # si el comprobante no tiene la percpci??n buscada se omite el registro
                if (amount_ret < 0.01) or (base_amount_ret < 0.01):       # si est?? el impuesto con valor = 0
                    continue

                #Inicio del registro
                v = ''

                # Campo 1 - Tipo de Operaci??n
                # 1: Retenci??n
                # 2: Percepci??n
                v = '1'

                # Campo 2 - C??digo de Norma
                v+= '029'

                # Campo 3 - Fecha de retenci??n/percepci??n - Formato: dd/mm/aaaa
                # v+= invoice.date_invoice.strftime("%d/%m/%Y")
                aux1=account_move_line.date
                aux1=datetime.strptime(aux1, '%Y-%m-%d')
                v+= aux1.strftime("%d/%m/%Y")

                # Campo 4 - Tipo de comprobante origen de la retenci??n
                # Si Tipo de Operaci??n =1 : 
                # 01 . Factura
                # 02 . Nota de D??bito
                # 03 . Orden de Pago
                # 04 . Boleta de Dep??sito
                # 05 . Liquidaci??n de pago
                # 06 . Certificado de obra
                # 07 . Recibo
                # 08 . Cont de Loc de Servic.
                # 09 . Otro ComprobanteTipo Comprobante 
                # Si Tipo de Operaci??n =2: 
                # 01 . Factura
                # 09 . Otro Comprobante
                v+= '03'

                # Campo 5 - Letra del Comprobante
                # Operaci??n Retenciones
                # Si Agente=R.I y Suj.Ret = R.I : Letra= A,M,B
                # Si Agente=R.I y Suj.Ret = Exento : Letra= C
                # Si Agente=R.I y Suj.Ret = Monot. : Letra= C
                # Si Agente=Exento y Suj.Ret=R.I : Letra= B
                # Si Agente=Exento y Suj.Ret=Exento : Letra= C
                # Si Agente=Exento y Suj.Ret=Monot. : Letra= C
                # Operaci??n Percepci??n
                # Si Agente=R.I y Suj.Ret = R.I : Letra= A,M,B
                # Si Agente=R.I y Suj.Ret = Exento : Letra= B
                # Si Agente=R.I y Suj.Ret = Monot. : Letra= B
                # Si Agente=R.I y Suj.Ret = No Cat. : Letra= B
                # Si Agente=Exento y Suj.Ret=R.I : Letra=C
                # Si Agente=Exento y Suj.Ret=Exento : Letra= C
                # Si Agente=Exento y Suj.Ret=Monot. : Letra= C
                # Si Agente=Exento y Suj.Ret=No Cat. : Letra=C
                # Si Tipo Comprobante = (01,06,07): A,B,C,M 
                # sino 1 d??gito blanco
                # jjvr - As?? estaba en el original 
                # if invoice.partner_id.afip_responsability_type_id.code == '4':
                #     v+= 'C'
                # else:
                #     if invoice.document_type_id.code == '1':
                #         v+= 'A'
                #     elif invoice.document_type_id.code == '6':
                #         v+= 'B'
                # jjvr - Se decide tomar la letra del documento de AFIP para percepcion
                v+= ' '

                # Campo 6
                inv_number = account_move_line.payment_id.document_number.replace('-','0')
                v+= inv_number.zfill(16)

                # Campo 7 - Fecha del comprobante - Formato: dd/mm/aaaa
                aux1=account_move_line.date
                aux1=datetime.strptime(aux1, '%Y-%m-%d')
                v+= aux1.strftime("%d/%m/%Y")

                # Campo 8 - Monto del comprobante total con impuestos incluidos
                # Decimales: 2
                # M??ximo: 9999999999999,99
                total_amount = invoice_amount_ret*currency_rate
                v+= str('%.2f'%round(total_amount,2)).replace('.',',').zfill(16)

                # Campo 9 - Nro de certificado propio
                # Si Tipo de Operaci??n = 1 se carga el Nro de certificado o blancos
                # Si Tipo de Operaci??n = 2 se completa con blancos.
                cert_ret=account_move_line.payment_id.withholding_number
                v+= cert_ret.rjust(16)

                # Campo 10 - Tipo de documento del Retenido
                # 3: CUIT
                # 2: CUIL
                # 1: CDI
                m_categ_id_code = account_move_line.partner_id.main_id_category_id.code 
                if m_categ_id_code == "CUIT":
                    tip_doc_ret='3'
                elif m_categ_id_code == "CUIL":
                    tip_doc_ret='2'
                elif m_categ_id_code == "CDI":
                    tip_doc_ret='2'
                else:
                    tip_doc_ret=''
                v+= tip_doc_ret
                
                # Campo 11 - Nro de documento del Retenido
                # Mayor a 0(cero)
                # M??ximo: 99999999999            
                v+= account_move_line.partner_id.main_id_number.replace('-','').zfill(11) 

                # Campo 12 - Situaci??n IB del Retenido
                # 1: Local 
                # 2: Convenio Multilateral
                # 4: No inscripto 
                # 5: Reg.Simplificado
                # Si Tipo de Documento=3: Situaci??n IB del Retenido=(1,2,4,5)
                # Si Tipo de Documento=(1,2): Situaci??n IB del Retenido=4
                # p_gross_income_type=invoice.partner_id.gross_income_type
                # if tip_doc_ret == '3':
                #     if p_gross_income_type == 'local':
                #         sit_ib_ret='1'
                #     elif p_gross_income_type == 'multilateral':
                #         sit_ib_ret='2'
                #     elif p_gross_income_type == 'no_liquida':
                #         sit_ib_ret='4'
                #     else:
                #         sit_ib_ret= '5'
                # else:
                #     sit_ib_ret='4'
                sit_ib_ret='5'
                v+= sit_ib_ret
                    
                # Campo 13 - Nro Inscripci??n IB del Retenido
                # Si Situaci??n IB del Retenido=4 : 00000000000
                # Se validar?? digito verificador.
                # 1.Local: 8 dig??tos N??mero + 2 d??gitos Verificador
                # 2. Conv.Multilateral: 3 d??gitos Jurisdicci??n + 6 d??gitos N??mero + 1 D??gito Verificador
                # 5. Reg.Simplificado: 2 d??gitos + 8 d??gitos + 1 d??gito verificador
                # if sit_ib_ret == '4':
                #     nro_inscr_ret='00000000000'
                # elif not invoice.partner_id.gross_income_number:
                #     nro_inscr_ret=invoice.partner_id.main_id_number.replace('-','').zfill(11)
                # else:
                #     nro_inscr_ret=str(invoice.partner_id.gross_income_number).replace('-','').zfill(11)                
                nro_inscr_ret=account_move_line.partner_id.main_id_number.replace('-','').zfill(11)
                v+= nro_inscr_ret

                # Campo 14 - Situaci??n frente al IVA del Retenido
                # 1 - Responsable Inscripto
                # 3 - Exento
                # 4 - Monotributo
                sit_iva_ret=''
                if account_move_line.partner_id.afip_responsability_type_id.code == '1':
                    sit_iva_ret= '1'
                elif account_move_line.partner_id.afip_responsability_type_id.code == '4':
                    sit_iva_ret= '3'
                else:
                    sit_iva_ret= '4'
                v+=sit_iva_ret

                # Campo 15 - Raz??n Social del Retenido
                lastname = account_move_line.partner_id.name[:30]
                lastname = lastname.ljust(30).replace(' ','_')
                v+= lastname

                # Calculo adicionales:
                # De acuerdo a la alicuota, base y monto de la percepcion
                # se toma como el monto de la percepci??n declarado en la contabilidad
                amount = round(amount_ret * currency_rate,2)
                alicuota = round((amount_ret / base_amount_ret * 100),2)
                base = round((base_amount_ret) ,2)
                vat_amount = round(vat_amount * currency_rate,2)
                imp_otr_vat = 0.00

                # Campo 16 - Importe otros conceptos
                # Decimales: 2
                # M??nimo: 0
                # M??ximo: 9999999999999,99
                # Importe Total del comprobante menos los conceptos de IVA
                v+= str('%.2f'%imp_otr_vat).replace('.',',').zfill(16)

                # Campo 17 - Importe IVA
                # Decimales: 2
                # M??nimo: 0
                # M??ximo: 9999999999999,99
                # Solo completar si Letra del Comprobante = (A,M)
                inv_letter = account_move_line.document_type_id.document_letter_id.name
                if (inv_letter == 'A') or (inv_letter == 'M'):
                    v+= str('%.2f'%vat_amount).replace('.',',').zfill(16)
                else:
                    v+= '0000000000000,00'

                # Campo 18 - Monto Sujeto a Retenci??n/ Percepci??n
                # Decimales: 2
                # M??nimo: 0
                # M??ximo: 9999999999999,99
                # Monto Sujeto a Retenci??n/ Percepci??n= (Monto del comprobante - Importe Iva - Importe otros conceptos)
                #base = mvt_per.base * currency_rate
                v+= str('%.2f'%base).replace('.',',').zfill(16)

                # Campo 19 -Al??cuota
                # Decimales: 2
                # M??nimo: 0
                # M??ximo: 99,99
                # Seg??n el Tipo de Operaci??n,C??digo de Norma y Tipo de Agente
                #alicuota = (mvt_per.amount / mvt_per.base * 100)
                v+= str('%.2f'%alicuota).replace('.',',').zfill(5)

                # Campo 20 - Retenci??n/Percepci??n Practicada
                # Decimales: 2
                # M??nimo: 0
                # M??ximo: 9999999999999,99
                # Retenci??n/Percepci??n Practicada= Monto Sujeto a Retenci??n/ Percepci??n * Al??cuota /100
                #amount = '%.2f'%round(mvt_per.amount  * currency_rate,2)
                v+= str('%.2f'%amount).replace('.',',').zfill(16)

                # Campo 21 - Monto Total Retenido/Percibido
                # Igual a Retenci??n/Percepci??n Practicada
                v+= str('%.2f'%amount).replace('.',',').zfill(16)

                # Campo 22
                v+= ' '*11

                lines.append(v)
        self.REGAGIP_CV_CBTE = '\r\n'.join(lines)

    def compute_agip_nc_data(self):
        # extraemos los comprobantes de notas de credito
        lines = []
        self.ensure_one()
        for invoice in self.invoice_ids:
            # si no es una nota de cr??dito es omite el registro ya que tiene otro formato el txt
            if invoice.document_type_id.internal_type != 'credit_note':
                continue
            mvt_per = None
            vat_amount = 0
            cantidad = 0
            if invoice.currency_id.id == invoice.company_id.currency_id.id:
                currency_rate = 1
            else:
                currency_rate = invoice.currency_rate
            for mvt in invoice.tax_line_ids:
                if mvt.tax_id.id == self.account_tax_per_id.id:
                    mvt_per = mvt
                if (mvt.tax_id.tax_group_id.type == 'tax') and (mvt.tax_id.tax_group_id.afip_code > 0):
                    vat_amount += mvt.amount
            if not mvt_per:                 # si no est?? el impuesto buscado 
                continue
            elif mvt_per.amount < 0.01:     # si est?? el impuesto pero con valor = 0
                continue

            #Inicio del registro
            v = ''

            # Campo 1 - Tipo de Operaci??n
            # 1: Retenci??n
            # 2: Percepci??n
            v = '2'

            # Campo 2 - Nro. Nota de cr??dito
            # Mayor a 0 (cero)
            # M??ximo: 999999999999
            inv_number = invoice.document_number.replace('-','')
            v+= inv_number.zfill(12)

            # Campo 3 - Fecha Nota de cr??dito 
            # Formato: dd/mm/aaaa
            aux1=invoice.date_invoice
            aux1=datetime.strptime(aux1, '%Y-%m-%d')
            v+= aux1.strftime("%d/%m/%Y")

            #C??lculos varios previos
            amount = round(mvt_per.amount  * currency_rate,2)
            alicuota = (mvt_per.amount / mvt_per.base * 100)
            total_amount = amount / alicuota * 100

            # Campo 4 - Monto nota de cr??dito
            # Mayor a 0 (cero)
            # Decimales: 2
            # M??ximo: 9999999999999,99
            # total_amount = invoice.amount_total*currency_rate
            v+= str('%.2f'%round(total_amount,2)).replace('.',',').zfill(16)

            # Campo 5 - Nro de certificado propio
            # Si Tipo de Operaci??n = 1 se carga el Nro de certificado o blancos
            # Si Tipo de Operaci??n = 2 se completa con blancos.
            v+= ' ' * 16

            # Campo 6 - Tipo de comprobante origen de la retenci??n
            # Si Tipo de Operaci??n =1 : 
            # 01 . Factura
            # 02 . Nota de D??bito
            # 03 . Orden de Pago
            # 04 . Boleta de Dep??sito
            # 05 . Liquidaci??n de pago
            # 06 . Certificado de obra
            # 07 . Recibo
            # 08 . Cont de Loc de Servic.
            # 09 . Otro ComprobanteTipo Comprobante 
            # Si Tipo de Operaci??n =2: 
            # 01 . Factura
            # 09 . Otro Comprobante
            v+= '01'

            # Campo 7 - Letra del Comprobante
            # Operaci??n Retenciones
            # Si Agente=R.I y Suj.Ret = R.I : Letra= A,M,B
            # Si Agente=R.I y Suj.Ret = Exento : Letra= C
            # Si Agente=R.I y Suj.Ret = Monot. : Letra= C
            # Si Agente=Exento y Suj.Ret=R.I : Letra= B
            # Si Agente=Exento y Suj.Ret=Exento : Letra= C
            # Si Agente=Exento y Suj.Ret=Monot. : Letra= C
            # Operaci??n Percepci??n
            # Si Agente=R.I y Suj.Ret = R.I : Letra= A,M,B
            # Si Agente=R.I y Suj.Ret = Exento : Letra= B
            # Si Agente=R.I y Suj.Ret = Monot. : Letra= B
            # Si Agente=R.I y Suj.Ret = No Cat. : Letra= B
            # Si Agente=Exento y Suj.Ret=R.I : Letra=C
            # Si Agente=Exento y Suj.Ret=Exento : Letra= C
            # Si Agente=Exento y Suj.Ret=Monot. : Letra= C
            # Si Agente=Exento y Suj.Ret=No Cat. : Letra=C
            # Si Tipo Comprobante = (01,06,07): A,B,C,M 
            # sino 1 d??gito blanco
            # jjvr - Se decide tomar la letra del documento de AFIP para percepcion
            inv_letter = invoice.document_type_id.document_letter_id.name
            v+= inv_letter

            # Campo 8 - Nro de comprobante
            # Mayor a 0 (cero)
            nro_comprob = invoice.document_number.replace('-','')
            v+= nro_comprob.zfill(16)

            # Campo 9 - Nro de documento del Retenido
            # Mayor a 0(cero)
            # M??ximo: 99999999999            
            if (invoice.partner_id.main_id_number>'') :
                v+= invoice.partner_id.main_id_number.replace('-','').zfill(11)
            else:
                v+='           '

            # Campo 10 - C??digo de Norma
            v+= '029'

            # Campo 11 - Fecha de retenci??n/percepci??n
            # Formato: dd/mm/aaaa
            aux1=invoice.date_invoice
            aux1=datetime.strptime(aux1, '%Y-%m-%d')
            v+= aux1.strftime("%d/%m/%Y")

            # Campo 12 - Ret/percep a deducir
            # Decimales: 2
            # M??nimo: 0
            # M??ximo: 9999999999999,99
            # Ret/percep a deducir = Monto nota de cr??dito * Al??cuota/100
            v+= str('%.2f'%amount).replace('.',',').zfill(16)

            # Campo 13 -Al??cuota
            # Decimales: 2
            # M??nimo: 0
            # M??ximo: 99,99
            # Seg??n el Tipo de Operaci??n,C??digo de Norma y Tipo de Agente
            v+= str('%.2f'%round(alicuota,2)).replace('.',',').zfill(5)

             # Campo ??
            # v+= ' '*9

            lines.append(v)
        self.REGAGIP_NC_CV_CBTE = '\r\n'.join(lines)

