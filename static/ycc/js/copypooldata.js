/**
 * Created by liushuansheng on 2015/7/7.
 */

var newIdcAutoComplete = null;

function copyPoolConfs() {
    var groupname = $('#s_group').val();
    var idc = $('#s_idc').val();
    var newgroupname = $('#s_newgroup').val();
    var newidc = $('#s_newidc').val();
    $.ajax({
        url:  cmdburl + 'ycc/copy/?format=json&groupname=' + groupname + '&idc=' + idc
                + '&newgroupname=' + newgroupname + '&newidc=' + newidc,
        type: 'POST',
        async:  false,
        headers: {'Authorization':'Token ' + apitoken},
        success: function( json ) {
            showSuccess(json.desc);
        },
        error: function( json ) {
            showError('复制配置组失败' + JSON.stringify(json.responseText));
        }
    });
}

function initBtn() {
    $('#copy_btn').bind('click', function() {
        if (idcAutoComplete == null || $('#s_idc').val() == '' || $('#s_newgroup').val() == '' || $('#s_newidc').val() == '') {
            showInfoDlg('请先选择配置组、IDC、新配置组和新IDC。');
        } else {
            copyPoolConfs();
        }
    });
}

function initIdc() {
    var newidclist = [{'text':'SH', 'value':'SH'}, {'text':'JQ', 'value':'JQ'}];
    $('#s_newidc').val('');
    if (newIdcAutoComplete)
        newIdcAutoComplete.destroy();
    newIdcAutoComplete = z.widget('AutoComplete', {
        renderTo: 's_newidc',
        dropDown: true,
        optionList: sortArr(newidclist),
        onSelected: function(t, v) {
        }
    });
}

function main(url, tocken) {
    cmdburl = url;
    apitoken = tocken;
    initQueryParas();
    initBtn();
    initIdc();
}
