##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, fields, api, exceptions, _
# from odoo.exceptions import ValidationError
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


    def compute_agip_data(self):
        # sacamos todas las lineas y las juntamos
        lines = []
        self.ensure_one()
        for invoice in self.invoice_ids:
            # si es una nota de crédito se omite el registro, ya que tiene otro formato el txt
            if invoice.document_type_id.internal_type == 'credit_note':
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
            # si el comprobante no tiene la percpción buscada se omite el registro
            if not mvt_per:                 # si no está el impuesto buscado 
                continue
            elif mvt_per.amount < 0.01:     # si está el impuesto pero con valor = 0
                continue

            #Inicio del registro
            v = ''

            # Campo 1 - Tipo de Operación
            # 1: Retención
            # 2: Percepción
            v = '2'

            # Campo 2 - Código de Norma
            v+= '029'

            # Campo 3 - Fecha de retención/percepción - Formato: dd/mm/aaaa
            # v+= invoice.date_invoice.strftime("%d/%m/%Y")
            aux1=invoice.date_invoice
            aux1=datetime.strptime(aux1, '%Y-%m-%d')
            v+= aux1.strftime("%d/%m/%Y")

            # Campo 4 - Tipo de comprobante origen de la retención
            # Si Tipo de Operación =1 : 
            # 01 . Factura
            # 02 . Nota de Débito
            # 03 . Orden de Pago
            # 04 . Boleta de Depósito
            # 05 . Liquidación de pago
            # 06 . Certificado de obra
            # 07 . Recibo
            # 08 . Cont de Loc de Servic.
            # 09 . Otro ComprobanteTipo Comprobante 
            # Si Tipo de Operación =2: 
            # 01 . Factura
            # 09 . Otro Comprobante
            v+= '01'

            # Campo 5 - Letra del Comprobante
            # Operación Retenciones
            # Si Agente=R.I y Suj.Ret = R.I : Letra= A,M,B
            # Si Agente=R.I y Suj.Ret = Exento : Letra= C
            # Si Agente=R.I y Suj.Ret = Monot. : Letra= C
            # Si Agente=Exento y Suj.Ret=R.I : Letra= B
            # Si Agente=Exento y Suj.Ret=Exento : Letra= C
            # Si Agente=Exento y Suj.Ret=Monot. : Letra= C
            # Operación Percepción
            # Si Agente=R.I y Suj.Ret = R.I : Letra= A,M,B
            # Si Agente=R.I y Suj.Ret = Exento : Letra= B
            # Si Agente=R.I y Suj.Ret = Monot. : Letra= B
            # Si Agente=R.I y Suj.Ret = No Cat. : Letra= B
            # Si Agente=Exento y Suj.Ret=R.I : Letra=C
            # Si Agente=Exento y Suj.Ret=Exento : Letra= C
            # Si Agente=Exento y Suj.Ret=Monot. : Letra= C
            # Si Agente=Exento y Suj.Ret=No Cat. : Letra=C
            # Si Tipo Comprobante = (01,06,07): A,B,C,M 
            # sino 1 dígito blanco
            # jjvr - Así estaba en el original 
            # if invoice.partner_id.afip_responsability_type_id.code == '4':
            #     v+= 'C'
            # else:
            #     if invoice.document_type_id.code == '1':
            #         v+= 'A'
            #     elif invoice.document_type_id.code == '6':
            #         v+= 'B'
            # jjvr - Se decide tomar la letra del documento de AFIP para percepcion
            inv_letter = invoice.document_type_id.document_letter_id.name
            v+= inv_letter

            # Campo 6
            inv_number = invoice.document_number.replace('-','0')
            v+= inv_number.zfill(16)

            # Campo 7 - Fecha del comprobante - Formato: dd/mm/aaaa
            aux1=invoice.date_invoice
            aux1=datetime.strptime(aux1, '%Y-%m-%d')
            v+= aux1.strftime("%d/%m/%Y")

            # Campo 8 - Monto del comprobante total con impuestos incluidos
            # Decimales: 2
            # Máximo: 9999999999999,99
            total_amount = invoice.amount_total*currency_rate
            v+= str('%.2f'%round(total_amount,2)).replace('.',',').zfill(16)

            # Campo 9 - Nro de certificado propio
            # Si Tipo de Operación =1 se carga el Nro de certificado o blancos
            # Si Tipo de Operación = 2 se completa con blancos.
            v+= ' ' * 16

            # Campo 10 - Tipo de documento del Retenido
            # 3: CUIT
            # 2: CUIL
            # 1: CDI
            m_categ_id_code = invoice.partner_id.main_id_category_id.code 
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
            # Máximo: 99999999999            
            v+= invoice.partner_id.main_id_number.replace('-','').zfill(11) 

            # Campo 12 - Situación IB del Retenido
            # 1: Local 
            # 2: Convenio Multilateral
            # 4: No inscripto 
            # 5: Reg.Simplificado
            # Si Tipo de Documento=3: Situación IB del Retenido=(1,2,4,5)
            # Si Tipo de Documento=(1,2): Situación IB del Retenido=4
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
                
            # Campo 13 - Nro Inscripción IB del Retenido
            # Si Situación IB del Retenido=4 : 00000000000
            # Se validará digito verificador.
            # 1.Local: 8 digítos Número + 2 dígitos Verificador
            # 2. Conv.Multilateral: 3 dígitos Jurisdicción + 6 dígitos Número + 1 Dígito Verificador
            # 5. Reg.Simplificado: 2 dígitos + 8 dígitos + 1 dígito verificador
            # if sit_ib_ret == '4':
            #     nro_inscr_ret='00000000000'
            # elif not invoice.partner_id.gross_income_number:
            #     nro_inscr_ret=invoice.partner_id.main_id_number.replace('-','').zfill(11)
            # else:
            #     nro_inscr_ret=str(invoice.partner_id.gross_income_number).replace('-','').zfill(11)                
            nro_inscr_ret=invoice.partner_id.main_id_number.replace('-','').zfill(11)
            v+= nro_inscr_ret

            # Campo 14 - Situación frente al IVA del Retenido
            # 1 - Responsable Inscripto
            # 3 - Exento
            # 4 - Monotributo
            sit_iva_ret=''
            if invoice.partner_id.afip_responsability_type_id.code == '1':
                sit_iva_ret= '1'
            elif invoice.partner_id.afip_responsability_type_id.code == '4':
                sit_iva_ret= '3'
            else:
                sit_iva_ret= '4'
            v+=sit_iva_ret

            # Campo 15 - Razón Social del Retenido
            lastname = invoice.partner_id.name[:30]
            lastname = lastname.ljust(30).replace(' ','_')
            v+= lastname

            # Calculo adicionales:
            # De acuerdo a la alicuota, base y monto de la percepcion
            # se toma como el monto de la percepción declarado en la contabilidad
            amount = round(mvt_per.amount * currency_rate,2)
            alicuota = round((mvt_per.amount / mvt_per.base * 100),2)
            base = round((amount / alicuota * 100) ,2)
            vat_amount = round(vat_amount * currency_rate,2)
            imp_otr_vat = total_amount - vat_amount - base

            # Campo 16 - Importe otros conceptos
            # Decimales: 2
            # Mínimo: 0
            # Máximo: 9999999999999,99
            # Importe Total del comprobante menos los conceptos de IVA
            v+= str('%.2f'%imp_otr_vat).replace('.',',').zfill(16)

            # Campo 17 - Importe IVA
            # Decimales: 2
            # Mínimo: 0
            # Máximo: 9999999999999,99
            # Solo completar si Letra del Comprobante = (A,M)
            if (inv_letter == 'A') or (inv_letter == 'M'):
                v+= str('%.2f'%vat_amount).replace('.',',').zfill(16)
            else:
                v+= '0000000000000,00'

            # Campo 18 - Monto Sujeto a Retención/ Percepción
            # Decimales: 2
            # Mínimo: 0
            # Máximo: 9999999999999,99
            # Monto Sujeto a Retención/ Percepción= (Monto del comprobante - Importe Iva - Importe otros conceptos)
            #base = mvt_per.base * currency_rate
            v+= str('%.2f'%base).replace('.',',').zfill(16)

            # Campo 19 -Alícuota
            # Decimales: 2
            # Mínimo: 0
            # Máximo: 99,99
            # Según el Tipo de Operación,Código de Norma y Tipo de Agente
            #alicuota = (mvt_per.amount / mvt_per.base * 100)
            v+= str('%.2f'%alicuota).replace('.',',').zfill(5)

            # Campo 20 - Retención/Percepción Practicada
            # Decimales: 2
            # Mínimo: 0
            # Máximo: 9999999999999,99
            # Retención/Percepción Practicada= Monto Sujeto a Retención/ Percepción * Alícuota /100
            #amount = '%.2f'%round(mvt_per.amount  * currency_rate,2)
            v+= str('%.2f'%amount).replace('.',',').zfill(16)

            # Campo 21 - Monto Total Retenido/Percibido
            # Igual a Retención/Percepción Practicada
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
            # si no es una nota de crédito es omite el registro ya que tiene otro formato el txt
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
            if not mvt_per:                 # si no está el impuesto buscado 
                continue
            elif mvt_per.amount < 0.01:     # si está el impuesto pero con valor = 0
                continue

            #Inicio del registro
            v = ''

            # Campo 1 - Tipo de Operación
            # 1: Retención
            # 2: Percepción
            v = '2'

            # Campo 2 - Nro. Nota de crédito
            # Mayor a 0 (cero)
            # Máximo: 999999999999
            inv_number = invoice.document_number.replace('-','')
            v+= inv_number.zfill(12)

            # Campo 3 - Fecha Nota de crédito 
            # Formato: dd/mm/aaaa
            aux1=invoice.date_invoice
            aux1=datetime.strptime(aux1, '%Y-%m-%d')
            v+= aux1.strftime("%d/%m/%Y")

            #Cálculos varios previos
            amount = round(mvt_per.amount  * currency_rate,2)
            alicuota = (mvt_per.amount / mvt_per.base * 100)
            total_amount = amount / alicuota * 100

            # Campo 4 - Monto nota de crédito
            # Mayor a 0 (cero)
            # Decimales: 2
            # Máximo: 9999999999999,99
            # total_amount = invoice.amount_total*currency_rate
            v+= str('%.2f'%round(total_amount,2)).replace('.',',').zfill(16)

            # Campo 5 - Nro de certificado propio
            # Si Tipo de Operación = 1 se carga el Nro de certificado o blancos
            # Si Tipo de Operación = 2 se completa con blancos.
            v+= ' ' * 16

            # Campo 6 - Tipo de comprobante origen de la retención
            # Si Tipo de Operación =1 : 
            # 01 . Factura
            # 02 . Nota de Débito
            # 03 . Orden de Pago
            # 04 . Boleta de Depósito
            # 05 . Liquidación de pago
            # 06 . Certificado de obra
            # 07 . Recibo
            # 08 . Cont de Loc de Servic.
            # 09 . Otro ComprobanteTipo Comprobante 
            # Si Tipo de Operación =2: 
            # 01 . Factura
            # 09 . Otro Comprobante
            v+= '01'

            # Campo 7 - Letra del Comprobante
            # Operación Retenciones
            # Si Agente=R.I y Suj.Ret = R.I : Letra= A,M,B
            # Si Agente=R.I y Suj.Ret = Exento : Letra= C
            # Si Agente=R.I y Suj.Ret = Monot. : Letra= C
            # Si Agente=Exento y Suj.Ret=R.I : Letra= B
            # Si Agente=Exento y Suj.Ret=Exento : Letra= C
            # Si Agente=Exento y Suj.Ret=Monot. : Letra= C
            # Operación Percepción
            # Si Agente=R.I y Suj.Ret = R.I : Letra= A,M,B
            # Si Agente=R.I y Suj.Ret = Exento : Letra= B
            # Si Agente=R.I y Suj.Ret = Monot. : Letra= B
            # Si Agente=R.I y Suj.Ret = No Cat. : Letra= B
            # Si Agente=Exento y Suj.Ret=R.I : Letra=C
            # Si Agente=Exento y Suj.Ret=Exento : Letra= C
            # Si Agente=Exento y Suj.Ret=Monot. : Letra= C
            # Si Agente=Exento y Suj.Ret=No Cat. : Letra=C
            # Si Tipo Comprobante = (01,06,07): A,B,C,M 
            # sino 1 dígito blanco
            # jjvr - Se decide tomar la letra del documento de AFIP para percepcion
            inv_letter = invoice.document_type_id.document_letter_id.name
            v+= inv_letter

            # Campo 8 - Nro de comprobante
            # Mayor a 0 (cero)
            nro_comprob = invoice.document_number.replace('-','')
            v+= nro_comprob.zfill(16)

            # Campo 9 - Nro de documento del Retenido
            # Mayor a 0(cero)
            # Máximo: 99999999999            
            v+= invoice.partner_id.main_id_number.replace('-','').zfill(11)

            # Campo 10 - Código de Norma
            v+= '029'

            # Campo 11 - Fecha de retención/percepción
            # Formato: dd/mm/aaaa
            aux1=invoice.date_invoice
            aux1=datetime.strptime(aux1, '%Y-%m-%d')
            v+= aux1.strftime("%d/%m/%Y")

            # Campo 12 - Ret/percep a deducir
            # Decimales: 2
            # Mínimo: 0
            # Máximo: 9999999999999,99
            # Ret/percep a deducir = Monto nota de crédito * Alícuota/100
            v+= str('%.2f'%amount).replace('.',',').zfill(16)

            # Campo 13 -Alícuota
            # Decimales: 2
            # Mínimo: 0
            # Máximo: 99,99
            # Según el Tipo de Operación,Código de Norma y Tipo de Agente
            v+= str('%.2f'%round(alicuota,2)).replace('.',',').zfill(5)

             # Campo ??
            # v+= ' '*9

            lines.append(v)
        self.REGAGIP_NC_CV_CBTE = '\r\n'.join(lines)

