(function(window, undefined) {
	dinggo = window.dinggo || {};

	dinggo.loading = function() {
	    this.init.apply(this, arguments);
    };
    dinggo.loading.prototype = {
	    options: {
	    	zIndex: 9999,
	    	opacity: 0.1,
	        loaded: function() {}
	    },
        init: function(opts) {
	        this.config = $.extend({}, this.options, opts);
	        this.create();
	    },    
	    create: function() {
	        var cfg = this.config;
            var dom_elem = [
                '<div class="loader-box">',
                    '<div class="ball-spin-fade-loader" >',
                          '<div></div>',
                          '<div></div>',
                          '<div></div>',
                          '<div></div>',
                          '<div></div>',
                          '<div></div>',
                          '<div></div>',
                          '<div></div>',
                    '</div>',
                '</div>'
            ].join('');
	        this.elem = $(dom_elem).appendTo('body');
	        //加入遮罩，加载状态中屏蔽其他event
	        this.mask = $('<div></div>').appendTo('body').css({
	            position: 'absolute',
	            zIndex: cfg.zIndex,
	            top: 0,
	            left: 0,
	            opacity: cfg.opacity,
	            backgroundColor: '#000',
	            height: '100%',
	            width: '100%'
	        });
    	},
	    destroy: function() {
	        this.elem.remove();
	        this.mask.remove();
	        this.config.loaded();
	    }
	}
})(window);