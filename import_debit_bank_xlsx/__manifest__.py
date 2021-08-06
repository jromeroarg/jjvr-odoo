{
    'name': "Import Debit Bank",
    "summary": "Import XLSX",
    "category": "Debit Management",
    'version':'0.1',
    "website": "http://www.jjvrsistemas.com.ar",
    "author": "jjvrsistemas",
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    'depends': ['base','mail','account','account_payment_group','l10n_ar',],
    # always loaded
    'data': [
        #'security/debit_bank_security.xml',
        # …Security Groups
        'security/ir.model.access.csv',
        # …Other data files
        'views/debit_bank_group_view.xml',
        'views/debit_bank.xml',
        'views/debit_bank_res_partner.xml',
        # 'views/account_payment_group_copy_view.xml',
        # 'views/templates.xml',
    ],
    # only loaded in demonstration mode
    # 'demo': [
    #     'demo/demo.xml',
    # ],
}
