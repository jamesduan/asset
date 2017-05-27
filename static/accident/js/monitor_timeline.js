/**
	*description:事故处理中心告警事件时间轴;
	*author:liuyating1;
	*date: 2017/4/18;
*/

var monitor_next = null;
var monitor_load_flag = true;
var monitor_post_arr = {};
//事件告警-事件类型下拉框加载
$.ajax({
    url: API_URL + 'notification/typelist/?format=json',
    headers: API_HEADERS,
    success: function( json ) {
        $.each(json, function(i, value) {
            $('#monitor_type').append('<option value="'+value.id+'">'+value.name+'</option>');
        });
        $('#monitor_type').selectpicker('refresh');
    }
});
//事件告警-事件来源下拉框加载
$.ajax({
    url: API_URL + 'notification/sourcelist/?format=json',
    headers: API_HEADERS,
    success: function( json ) {
        $.each(json, function(i, value) {
            $('#monitor_source').append('<option value="'+value.id+'">'+value.name+'</option>');
        });
        $('#monitor_source').selectpicker('refresh');
    }
});
//事件告警-事件等级下拉框加载
$.ajax({
    url: API_URL + 'notification/levellist/?format=json&id__lt=400',
    headers: API_HEADERS,
    success: function( json ) {
        $.each(json, function(i, value) {
            $('#monitor_level').append('<option value="'+value.id+'">'+value.name+'</option>');
        });
        $('#monitor_level').selectpicker('refresh');
    }
});

//告警事件时间轴条件筛选时间轴数据
$('.monitor_url').change(function(){
    change_Monitor();
});
$('#monitor_select_submit').click(function(){
    change_Monitor();
});
$('#monitor_select_reset').click(function(){
    $('.mform_url').val('');
    $('.mform_url').selectpicker('refresh');
    change_Monitor();
});

//分页获取告警事件记录
function updateMonitorLine(url, ids_arr, loading_position) {
    if(loading_position== 'center'){
        $('.loader-box .ball-spin-fade-loader').css({display: ''});
    }else{
        $('.loader-box-bottom .ball-spin-fade-loader').css({display: ''});
    }
    $.ajax({
        url: url,
        type: "GET",
        async: false,
        timeout : 3000,
        headers: API_HEADERS,
        success: function (monitor_res) {
            if(loading_position== 'center'){
                $('.loader-box .ball-spin-fade-loader').css({display: 'none'});
            }else{
                $('.loader-box-bottom .ball-spin-fade-loader').css({display: 'none'});
            }
            if(monitor_res.count > 0){
                $.each(monitor_res.results, function (i, val) {
                    var happen_time = moment(val['get_time'], 'X').format('YYYY-MM-DD HH:mm:ss');
                    var site_name = val['event_detail'].length>0 && val['event_detail'][0]['site_name'] != null ? val['event_detail'][0]['site_name'] : '';
                    var pool_name = val['event_detail'].length>0 && val['event_detail'][0]['site_name'] != null ? val['event_detail'][0]['pool_name'] : '';
                    var site_app = (site_name.trim() != '' && pool_name.trim() != '') ? site_name + '/' + pool_name : ''
                    var ips = val['event_detail'].length>0 ? val['event_detail'][0]['ip'] : '';
                    var ips_html = ips.length > 0 ? '<p>IP:' + ips + '</p>' : '';
                    monitor_post_arr[val['id']] = {
                        'app_id': val['pool_id'],
                        'ip': ips,
                        'level_id': val['level_id'],
                        'message': '【'+ val['source_name'] + '】【' + val['type_name'] + '】 ' + site_app + ' ' + val['message'] + ' <a href="{{ monitor_url }}event/?id=' + val["id"] + '" target="_blank" title="点击查看详情">详情</a> ',
                        'happened_time': val['get_time']
                    }
                    var push_icon = '<div class="tool_bar"><a id="monitor-'+val['id']+'" title="推送告警信息到事故log"  data-pushid="'+ val['id'] +'"><span class="glyphicon glyphicon-share"></span></a></div>';
                    if($.inArray(val['id'], ids_arr) != -1){
                        push_icon = '<div class="tool_bar"><a class="checked" title="已推送至事故处理主时间轴"  data-pushid="'+ val['id'] +'"><span class="glyphicon glyphicon-share"></span></a></div>';
                    }
                    $('#monitorLine').append('<div class="node_item level0'+ val['level_id'] +' cur"> <span class="node_time">' + happen_time + '</span> <div class="node_right level0'+ val['level_id'] +'"> ' +
                        '<div class="node_info"> <ul class="clearfix"> <li><label for="">来源：</label><span>' + val['source_name'] + '</span></li><li><label for="">类型：</label><span>' + val['type_name'] + '</span></li>' +
                            '<li><label for="">应用：</label><span>' + site_app + '</span></li><li><label for="">等级：</label><span>' + val['level_name'] + '</span></li> </ul>' +
                        '<div class="describe">' + ips_html + '<p>' + val['message'] + '</p> </div>' + push_icon + '</div> </div> </div>');
                    pushClickMonitor('monitor-' + val['id']);
                });
            }else{
                $('#monitorLine').append('<div class="node_item level00 cur"> <div class="node_right level00"> ' +
                            '<div class="node_info"><div class="alldescribe"> <p>无告警事件记录</p> </div> </div> </div> </div>');
            }
            if(monitor_res.next == null){
                $('#monitorLine').append('<a href="javascript:;" class="gray_btn">END</a>')
            }
            //滚动加载
            monitor_next = monitor_res.next;
        }
    });
    //解锁状态为可加载
    monitor_load_flag = true;
}
//告警事件默认加载
function change_Monitor() {
    var monitor_api_url = API_URL + 'notification/event/';
    var source = $('#monitor_source').val();
    var type = $('#monitor_type').val();
    var level = $('#monitor_level').val();
    var app_id = $('#monitor_app_id').val();
    var start_time = $('#monitor_start_time').val();
    var end_time = $('#monitor_end_time').val();
    var params = ['?format=json&page_size=20&page=1', 'exclude_source_id=6', 'level_id=400'];
    if(source != ''){
        params.push('source__id=' + source)
    }
    if(type != ''){
        params.push('type__id=' + type)
    }
    if(level != ''){
        params.push('level__id=' + level)
    }
    if(app_id != ''){
        params.push('pool_id=' + app_id)
    }
    if(start_time != ''){
        params.push('start_time=' + start_time)
    }
    // else{
    //     params.push('start_time=' + moment().subtract(30,"minute").format('YYYY-MM-DD HH:mm:ss'));
    // }
    if(end_time != ''){
        params.push('end_time=' + end_time)
    }else{
        params.push('end_time=' + moment().format('YYYY-MM-DD HH:mm:ss'));
    }
    $('#monitorLine').html('');
    if (monitor_load_flag) {
        //锁定状态为加载中
        monitor_load_flag = false;
        updateMonitorLine(monitor_api_url + params.join('&'), get_change_ids(2), 'center');
    }
}

//筛选条件更改刷新时间轴
$('#monitor_app_id').on('change', function (e) {
    change_Monitor();
});

//推送告警事件记录到事故处理时间轴
function pushClickMonitor(id){
    $('#'+id).click(function(){
        var $this = $(this);
        var monitor = monitor_post_arr[$(this).data('pushid')];
        $.ajax({
            url: API_URL + 'accident/log/',
            type: 'POST',
            async:  false,
            data: {
                'accident_id': cur_accident_id,
                'source': 2,
                'from_id': $(this).data('pushid'),
                'username': logined_username,
                'app_id': monitor['app_id'],
                'ip': monitor['ip'],
                'level_id': monitor['level_id'],
                'message': monitor['message'],
                'happened_time': monitor['happened_time']
            },
            headers: API_HEADERS,
            success: function( res ) {
                toastr.success("成功推送至事故log！");
                $this.addClass('checked');
            },
            error: function( json ) {
                swal("", '推送log失败，原因：' + JSON.stringify(JSON.parse(json.responseText)['detail']), "error");
            }
        });
    });
}