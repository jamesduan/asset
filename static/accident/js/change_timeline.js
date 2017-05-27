/**
	*description:事故处理中心配置变更时间轴;
	*author:liuyating1;
	*date: 2017/4/18;
*/
var change_next = null;
var change_load_flag = true;
var change_post_arr = {};

$('.selectpicker').selectpicker({
	'width': 'auto'
});

$('#app, #change_app').selectpicker({
	'width': '190px',
	'liveSearch': true,
	'liveSearchPlaceholder': '搜索Pool',
	'size': 10
});
$('.selectTime').datetimepicker({
	format: 'yyyy-mm-dd hh:ii:ss',
	weekStart: 1,
	todayHighlight: 1,
	autoclose: true,
	minView: 2,
	hourStep: 1,
});

//配置变更-变更类型下拉框加载
var change_types = new Array();
$.ajax({
	url: API_URL + 'cmdbv2/change/type/?format=json&level_id__in=1,2',
	headers: API_HEADERS,
	success: function( json ) {
		$.each(json, function(i, value) {
			$('#change_type').append('<option value="'+value.id+'">'+value.name+'</option>')
			change_types.push({
				'id': value.id,
				'name': value.name,
			});
		});
		$('#change_type').selectpicker('refresh')
	}
});
//配置变更-变更动作下拉框加载
var change_actions = new Array();
$.ajax({
	url: API_URL + 'cmdbv2/change/action/?format=json&level_id__in=1,2',
	headers: API_HEADERS,
	success: function( json ) {
		$.each(json, function(i, value) {
			$('#change_action').append('<option value="'+value.id+'">'+value.name+'</option>')
			change_actions.push({
				'id': value.id,
				'name': value.name,
				'type_id': value.type_id,
				'type_name': value.type_name
			});
		});
		$('#change_action').selectpicker('refresh')
	}
});

//配置变更的select框二级联动
$('#change_type').change(function(){
	var type_id = $('#change_type option:selected').val();
	$('#change_action').find('option').remove();
	$('#change_action').append($('<option>').text('变更动作').attr('value', ''));
	if(type_id != ""){
		$.each(change_actions, function(i, value) {
			if(value['type_id'] == type_id){
				$('#change_action').append('<option value="'+value['id']+'">'+value['name']+'</option>');
			}
		});
	}else {
		$.each(change_actions, function(i, value) {
			$('#change_action').append('<option value="'+value['id']+'">'+value['name']+'</option>');
		});
	}
	$('#change_action').selectpicker('refresh');
});

//配置变更时间轴条件筛选时间轴数据
$('.change_url').change(function(){
	change_Change();
});
$('#change_select_submit').click(function(){
	change_Change();
});
$('#change_select_reset').click(function(){
	$('.cform_url').val('');
	$('#change_action').find('option').remove();
	$('#change_action').append($('<option>').text('变更动作').attr('value', ''));
	$.each(change_actions, function(i, value) {
		$('#change_action').append('<option value="'+value['id']+'">'+value['name']+'</option>');
	});
	$('.cform_url').selectpicker('refresh');
	change_Change();
});

//筛选条件更改刷新时间轴
$('#change_app').on('change', function (e) {
	change_Change();
});

//分页获取配置变更记录
function updateChangeLine(url, ids_arr, loading_position) {
	if(loading_position== 'center'){
		$('.loader-box .ball-spin-fade-loader').css({display: ''});
	}else{
		$('.loader-box-bottom .ball-spin-fade-loader').css({display: ''});
	}
	$.ajax({
		url: url,
		type: "GET",
		async: false,
		timeout: 3000,
		headers: API_HEADERS,
		success: function (change_res) {
			if(loading_position== 'center'){
				$('.loader-box .ball-spin-fade-loader').css({display: 'none'});
			}else{
				$('.loader-box-bottom .ball-spin-fade-loader').css({display: 'none'});
			}
			if(change_res.count > 0){
				$.each(change_res.results, function (i, val) {
					var message = '【'+ val['action_type_name'] + '】 【' + val['action_name'] + '】 '+ val['user'] + ' '  + val['pool_name'] +  ' <a href="{{ cmdbv2_url }}change/changelist/?id=' + val["id"] + '" target="_blank" title="点击查看详情">' + val['index'] +'</a>'
					change_post_arr[val['id']] = {
						'app_id': 1,
						'level_id': 3,
						'message': message,
						'happened_time': moment(val['happen_time_str'], 'YYYY-MM-DD HH:mm:ss').format('X')
					}
					var push_icon = '<div class="tool_bar"><a id="change-' + val['id'] + '" title="推送变更信息到事故log" data-pushid="'+ val['id'] +'"><span class="glyphicon glyphicon-share"></span></a></div>';
					if($.inArray(val['id'], ids_arr) != -1){
						push_icon = '<div class="tool_bar"><a class="checked" title="已推送至事故处理主时间轴"  data-pushid="'+ val['id'] +'"><span class="glyphicon glyphicon-share"></span></a></div>';
					}
					$('#changeLine').append('<div class="node_item level0'+ val['level_id'] +' cur"> <span class="node_time">' + val['happen_time_str'] + '</span> <div class="node_right level0'+ val['level_id'] +'"> ' +
						'<div class="node_info"> <ul class="clearfix"> <li><label for="">动作：【</label><span>' + val['action_type_name'] + '】【'+ val['action_name'] + '】</span></li><li><label for="">应用：</label><span>' + val['pool_name'] + '</span></li> <li><label for="">变更人：</label><span>' + val['user'] + '</span></li>' +
							'<li><label for="">索引值：</label><span>' + val['index'] + '</span></li> </ul> ' +
						'<div class="describe"> <p>' + val['message'] + '</p> </div>' + push_icon + '</div> </div> </div>');
					pushClickChange('change-' + val['id']);
				});

			}else{
				$('#changeLine').append('<div class="node_item level00 cur"> <div class="node_right level00"> ' +
							'<div class="node_info"><div class="alldescribe"> <p>无配置变更记录</p> </div> </div> </div> </div>');
			}
			if(change_res.next == null){
				$('#changeLine').append('<a href="javascript:;" class="gray_btn">END</a>')
			}
			//滚动加载的URL
			change_next = change_res.next;
		}
	});
	//解锁状态为可加载
	change_load_flag = true;
}
//配置变更默认加载
function change_Change() {
	var change_api_url = API_URL + 'change/changelist/'
	var type = $('#change_type').val();
	var action = $('#change_action').val();
	var app_id = $('#change_app').val();
	var index = $('#change_index').val();
	var start_time = $('#change_start_time').val();
	var end_time = $('#change_end_time').val();
	var params = ['?format=json&page_size=20&page=1&level_id__lt=3'];

	if(type != ''){
		params.push('type_id=' + type)
	}
	if(action != ''){
		params.push('action_id=' + action)
	}
	if(app_id != ''){
		params.push('app_id=' + app_id)
	}
	if(index != ''){
		params.push('index=' + index)
	}
	if(start_time != ''){
		params.push('start_time=' + moment(start_time).format('X'));
	}
	if(end_time != ''){
		params.push('end_time=' + moment(end_time).format('X'));
	}else{
		params.push('end_time=' + (moment().format('X')));
	}
	$('#changeLine').html('');
	if(change_load_flag) {
		//锁定状态为加载中
		change_load_flag = false;
		updateChangeLine(change_api_url + params.join('&'), get_change_ids(1), 'center');
	}
}

//推送配置变更记录到事故处理时间轴
function pushClickChange(id){
	$("#" + id).click(function(){
		var $this = $(this);
		var change = change_post_arr[$(this).data('pushid')];
		$.ajax({
			url:API_URL + 'accident/log/',
			type: 'POST',
			async:  false,
			timeout : 3000,
			data: {
				'accident_id': cur_accident_id,
				'source': 1,
				'from_id': $(this).data('pushid'),
				'username': logined_username,
				'app_id': change['app_id'],
				'level_id': change['level_id'],
				'message': change['message'],
				'happened_time': change['happened_time']
			},
			headers:  API_HEADERS,
			success: function( res ) {
				toastr.success("成功推送至事故log！");
				$this.attr("class", 'checked');
			},
			error: function( json ) {
				swal("", '推送log失败，</strong>原因：' + JSON.stringify(JSON.parse(json.responseText)['detail']), "error");
			}
		});
	});
}
