odoo.define('pos_payment_ref.popups', function (require) {
"use strict";

var PopupWidget = require('point_of_sale.popups');
var gui = require('point_of_sale.gui');

var PaymentInfoWidget = PopupWidget.extend({
    template: 'PaymentInfoWidget',
    show: function(options){
        options = options || {};
        this._super(options);
        this.renderElement();

        // begin add - paso 3 - paso de variable a pos_payment_ref.xml
        // utilizamos la variable widget.options.pos_payment_type.
        // end add

        $('body').off('keypress', this.keyboard_handler);
        $('body').off('keydown', this.keyboard_keydown_handler);
        window.document.body.addEventListener('keypress',this.keyboard_handler);
        window.document.body.addEventListener('keydown',this.keyboard_keydown_handler);
        if(options.data){
            var data = options.data;
            this.$('input[name=payment_ref]').val(data.payment_ref);
            this.$('input[name=cupon]').val(data.cupon);
            this.$('input[name=lote]').val(data.lote);
        }
    },
    click_confirm: function(){
        var infos = {
            'payment_ref' : this.$('input[name=payment_ref]').val(),
            'cupon' : this.$('input[name=cupon]').val(),
            'lote' : this.$('input[name=lote]').val(),
        };
        var valid = true;
        if(this.options.validate_info){
            valid = this.options.validate_info.call(this, infos);
        }

        this.gui.close_popup();
        if( this.options.confirm ){
            this.options.confirm.call(this, infos);
        }
    },
});
gui.define_popup({name:'payment-info-input', widget: PaymentInfoWidget});

return PopupWidget;
});