/*
	*description:乐道;
	*author:liuyating1;
	*date: 2016/12/06;
	*update:
*/

var ldScript = {
initFun:function(){
	this.ldTabfun();
	this.filtrateFun();
	this.editAccidentNameFun();
	this.suspectedProblemPoolFun();
	this.popFun();
	this.recipientsFun();
	this.hasTooltip();
	this.checkedIcon();
},
ldTabfun:function(){
	$('.ld_left_tab .tool').on('click',function(){
		$(this).addClass('cur').siblings().removeClass('cur');
		$(this).parents('.ld_left_bar').siblings('.ld_tab_body').find('.ld_tab_item').eq($(this).index()).show().siblings().hide();
	});
},
//筛选
filtrateFun:function(){
	//下拉框
	$('li','.dropdown-menu').on('click',function(){
		var value = $(this).find('a').html();
		$(this).parents('.dropdown-menu').siblings('.ipt_txt').html(value);
	});
	//选择开始时间
	$(".form_datetime").datetimepicker({
		format: 'yyyy-mm-dd hh:ii',
		autoclose: 1
	});
	//筛选按钮
	$('.filtrate_btn').on('click',function(){
		if($(this).hasClass('clean_btn')){
			$(this).removeClass('clean_btn').html('筛选');
		}else{
			$(this).addClass('clean_btn').html('清除');
		}
	});
},
//编辑事故名称
editAccidentNameFun:function(){
	$('i','.display_box').on('click',function(){
		var oldName = $(this).siblings('h2').html(),
				editBox = $(this).parent('.display_box').siblings('.edit_box');
		editBox.find('input').val(oldName);
		editBox.show();
	});
	//确定修改
	$('.confirm_modify').on('click',function(){
		var nowName = $(this).siblings('input').val();
		nowName = $.trim(nowName);
		if(nowName){
			nowName = $(this).siblings('input').val();
			$(this).parent('.edit_box').siblings('.display_box').find('h2').html(nowName);
		}else{
			alert('事故名不能为空！');
		}
		$(this).parent('.edit_box').hide();
	});
	//取消修改
	$('.cancel_modify').on('click',function(){
		$(this).parent('.edit_box').hide();
	});
},
//疑似问题pool
suspectedProblemPoolFun:function(){
	$('li','.problem_list').on('click',function(){
		var _this=$(this);
		var li=$('.problem_list').children('li');
		var btn=$('.problem_list').siblings('.pool_btn_box').find('.gray_box .hand_btn');
		_this.toggleClass('cur');
		if(li.hasClass('cur')){
			btn.removeClass('gray_hand');
		}else{
			btn.addClass('gray_hand');
		}
	});
	//添加pool
	$('.add_pool_btn').on('click',function(){
		$(this).siblings('.form_box').fadeIn();
	});
	//下拉框
	$('li','.dropdown-menu').on('click',function(){
		var value = $(this).find('a').html();
		$(this).parents('.input-group-btn').siblings('.ipt_txt').val(value);
	});
	//关闭tool_tip
	function closeToolTip(){
		$('.form_box').fadeOut();
	}
	$('.tool_tip_cl').on('click',function(){
		closeToolTip();
	})
},
//弹窗
popFun:function(){
	//邮件通知
	$('.ld_email').click(function(){
		$('.ld_pop_common').hide();
		$('.ld_email_pop').show();
	});
	//关闭事故
	$('.close_accident').click(function(){
		$('.ld_pop_common').hide();
		$('.close_accident_pop').show();
	});
	//查看图片弹框
	$('.look_img').click(function(){
		$('.ld_pop_common').hide();
		$('.look_img_pop').show();
		//获取页面高度
		var height=$(document).height();
		$('.look_img_pop,.mask_pop').css("height",height);
	});
	//录入
	$('.entry_btn').click(function(){
		$('.ld_pop_common').hide();
		$('.entry_btn_pop').show();
		//点击显示连接弹框
		$('.entry_btn_pop').on('click','.icon-lianjie',function(){
			$(this).next('.form_box').show();
		});

	});
	//点击关闭弹框
	$('.ld_pop_common').on('click','.close_btn',function(){
		$(this).parents('.ld_pop_common').find('input,textarea').val('');
		$(this).parents('.ld_pop_common').hide();
	});
	//弹窗最小化
	$('.ld_pop_common').on('click','.icon-zuixiaohua',function(){
		$(this).parents('.pop_head').addClass('pop_hd').next('.fade_cont').addClass('none');
		$(this).addClass('icon-fangda').removeClass('icon-zuixiaohua');
	});
	//弹窗最大化
	$('.ld_pop_common').on('click','.icon-fangda',function(){
		$(this).parents('.pop_head').removeClass('pop_hd');
		$(this).parents('.ld_pop_common').children('.fade_cont').removeClass('none');
		$(this).addClass('icon-zuixiaohua').removeClass('icon-fangda');
	});

},
//收件人
recipientsFun:function(){
	function showDrop(target){
		var w=$(window).width();
		var h=$(window).height();
		var wOffset=target.offset().left;
		var hOffset=parseInt(target.offset().top);
		var _width=parseInt(w-wOffset);
		var _height=parseInt(h-hOffset);
		var select=target.parents('.recipient_main').siblings('.drop_box');
		var width=select.outerWidth(true);
		var height=select.outerHeight(true);

		var now_top = parseInt(target.parents('.recipient_main').find('.choosed_people').outerHeight(true)) + 10;
		if(target.parents('.recipient_main').find('.choosed_people').outerHeight(true) >= target.parents('.recipient_main').outerHeight(true)){
			now_top = target.parents('.recipient_main').outerHeight(true)
		}
		select.css({
			'top' : now_top
		})
		if (target.parents('.recipient_main').hasClass('copy_to')) {
			select.css({
				'top' : '',
				'bottom' : '100%'
			})
		}
		select.show();
	}
	function closeDrop(){
		$('.drop_box').hide();
	}
	//输入框获取焦点
	$('.recipient_ipt').on('focus',function(){
		showDrop($(this));
	});
	//下拉选项选择
	$('li','.drop_box').click(function(){
		var _iptVal=$(this).find('.name_spell').html();
		var _html=
			'<div class="people_name">'+
			'<span>'+_iptVal+'</span>'+
			'<a href="javascript:;" class="delete">&times;</a>'+
			'</div>';
		$(this).parents('.drop_box').siblings('.recipient_main').find('.drop_select').before(_html);
		// $(this).parents('.drop_select').before(_html);
		// ipt.val('');
		// closeDrop();
	});
	//点击空白关闭下拉框
	$(document).on('click',function(e){
		e.stopPropagation();
		if($(e.target).closest('.drop_select').length == 0){
			closeDrop();
		}
	});
	//删除收件人
	$('.ld_pop_common').on('click','.delete',function(){
		$(this).parents('.people_name').remove();
	});
},
//hover显示事故内容
hasTooltip:function(){
	$('.accident_cont .has_tooltip').hover(function(){
		var _this=$(this).children('.incident'),
			hoverCont=$(this).children('.incident_cont');
		hoverCont.show();
		var w=window.innerWidth-$(document).scrollLeft(),
			thisOffset=_this.offset().left,
			_width=_this.outerWidth(),
			width=parseInt(w-thisOffset-_width),
			hoverWidth=hoverCont.outerWidth();
		if(width<hoverWidth){
			hoverCont.addClass('laft_show').removeClass('center_show');
		}else if(width<hoverWidth && thisOffset<hoverWidth){
			hoverCont.removeClass('laft_show').addClass('center_show');
		}else{
			hoverCont.removeClass('laft_show').removeClass('center_show');
		}
	},function(){
		$(this).children('.incident_cont').hide();
	});
},
//点击图标
checkedIcon:function(){
	$('.icon_point').on('click',function(){
		$(this).addClass('checked');
	});
}
}
ldScript.initFun();