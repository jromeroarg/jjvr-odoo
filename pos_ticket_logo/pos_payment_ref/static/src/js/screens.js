odoo.define('pos_payment_ref.screens', function (require) {
"use strict";

var screens = require('point_of_sale.screens');

screens.PaymentScreenWidget.include({
    show_popup_payment_info: function(options) {
        var self = this;
        window.document.body.removeEventListener('keypress', self.keyboard_handler);
        window.document.body.removeEventListener('keydown', self.keyboard_keydown_handler);
        this.gui.show_popup('payment-info-input',{

            // begin add - paso 2 - paso pos_payment_type a popus.js
            'pos_payment_type': options.pos_payment_type,
            // end add

            data: options.data,
            validate_info: function(infos){
                this.$('input').removeClass('error');
                if(!infos.bank_name) {
                    this.$('input[name=payment_ref]').addClass('error');
                    this.$('input[name=payment_ref]').focus();
                    this.$('input[name=cupon]').addClass('error');
                    this.$('input[name=cupon]').focus();
                    this.$('input[name=lote]').addClass('error');
                    this.$('input[name=lote]').focus();
                    return false;
                }
//                }
                return true;
            },
            confirm: function(infos){
                options.confirm.call(self, infos);
                self.reset_input();
                self.render_paymentlines();
                window.document.body.addEventListener('keypress', self.keyboard_handler);
                window.document.body.addEventListener('keydown', self.keyboard_keydown_handler);
            },
            cancel: function(){
                window.document.body.addEventListener('keypress', self.keyboard_handler);
                window.document.body.addEventListener('keydown', self.keyboard_keydown_handler);
            },
        });
    },
    click_paymentmethods: function(id) {
        var self = this;
        var cashregister = null;
        for ( var i = 0; i < this.pos.cashregisters.length; i++ ) {
            if ( this.pos.cashregisters[i].journal_id[0] === id ){
                cashregister = this.pos.cashregisters[i];
                break;
            }
        }
        if (cashregister.journal.pos_payment_ref) {
            this.show_popup_payment_info({
                confirm: function(infos) {
                    //merge infos to new paymentline
                    self.pos.get_order().add_paymentline_with_details(cashregister, infos);
                },

                // begin add - paso 1 - inicio de secuencia
                // guardo valor en variable pos_payment_type 
                // y se lo paso a la funcion show_popup_payment_info de screens.js
                'pos_payment_type': cashregister.journal.pos_payment_type,
                // end add
                
            });
        }
        else {
            this._super(id);
        }
    },

    click_numpad: function(button) {
        var paymentlines = this.pos.get_order().get_paymentlines();
        var open_paymentline = false;

        for (var i = 0; i < paymentlines.length; i++) {
            if (! paymentlines[i].paid) {
                open_paymentline = true;
            }
        }

        if (! open_paymentline) {
            var cashregister = null;
            for ( var i = 0; i < this.pos.cashregisters.length; i++ ) {
                if (!this.pos.cashregisters[i].journal.pos_payment_ref){
                    cashregister = this.pos.cashregisters[i];
                    break;
                }
            }
            this.pos.get_order().add_paymentline(cashregister);
            this.render_paymentlines();
        }

        this.payment_input(button.data('action'));
    },

    click_payment_info_paymentline: function(cid){
        var self = this;
        var lines = this.pos.get_order().get_paymentlines();
        for ( var i = 0; i < lines.length; i++ ) {
            if (lines[i].cid === cid) {
                this.show_popup_payment_info({
                    data: lines[i],
                    confirm: function(infos) {
                        //merge infos to updated paymentline
                        self.pos.get_order().update_paymentline_with_details(lines[i], infos);
                    },
                });
                return;
            }
        }
    },

    render_paymentlines: function() {
        var self = this;
        this._super();
        var lines = this.$('.paymentlines-container table.paymentlines');
        lines.on('click','.payment-info-button', function(){
            self.click_payment_info_paymentline($(this).data('cid'));
        });
    }

});

});
