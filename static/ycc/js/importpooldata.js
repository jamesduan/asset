/**
 * Created by liushuansheng on 2015/6/23.
 */

var oldGroupAutoComplete = null;
var oldIdcAutoComplete = null;

function initSrcIdcAutoComplete(srcidclist) {
    if (oldIdcAutoComplete)
        oldIdcAutoComplete.destroy();
    oldIdcAutoComplete = z.widget('AutoComplete', {
        renderTo: 's_srcidc',
        dropDown: true,
        optionList: sortArr(srcidclist),
        onSelected: function(t, v) {
        }
    });
    if (srcidclist.length == 1)
        $('#s_srcidc').val(srcidclist[0].text);
}

function initSrcGroupAutoComplete(json) {
    var srcgrouplist = [];
    $.each(json.results, function(index, value) {
        srcgrouplist.push({
            text:value.group_id,
            value:value
        });
    });
    if (oldGroupAutoComplete)
        oldGroupAutoComplete.destroy();
    oldGroupAutoComplete = z.widget('AutoComplete', {
        renderTo: 's_srcgroup',
        dropDown: true,
        optionList: sortArr(srcgrouplist),
        onSelected: function(t, v) {
            var srcidclist = [];
            srcidclist.push({
                text: v.idc,
                value: v
            });
            initSrcIdcAutoComplete(srcidclist);
        }
    });
}

function initSrcGroupAutoCompleteEvent() {
    $('#s_srcgroup').bind('keyup', function() {
        if($(this).val() == '') {
            if (oldIdcAutoComplete) {
                oldIdcAutoComplete.destroy();
                oldIdcAutoComplete = null;
            }
            $('#s_srcidc').val('');
            $('#s_srcidc').prop("title", "");
        }
    });
    $('#s_srcgroup').val('');
    $('#s_srcdc').val('');
}

function initSrcGroup() {
    initSrcGroupAutoCompleteEvent();
    $.ajax({
        url: cmdburl + 'ycc/oldgroup/?format=json&page_size=5000&page=1',
        type: 'GET',
        async: false,
        headers: {'Authorization':'Token ' + apitoken},
        success: function ( json ) {
            initSrcGroupAutoComplete(json);
        },
        error: function ( json ) {
            showError('查询配置组失败' + JSON.stringify(json.responseText));
        }
    });
}


function importPoolConfs(srcgroup, dstgroup, dstidc) {
    $.ajax({
        url: '{{ CMDBAPI_URL }}ycc/import/?format=json&srcgroup=' +
            srcgroup + '&dstgroup=' + dstgroup + '&dstidc=' + dstidc,
        type: 'POST',
        async:  false,
        headers: {'Authorization':'Token  {{ API_TOKEN }}'},
        success: function( json ) {
            var idcname = $('#s_idc').val();
            var desc = '从' + srcgroup  + '导入到' + dstgroup + ':' + dstidc;
            desc += '</br>导入源环境为: ' + json.envs;
            desc += '</br>导入' + json.dataidnum + '个配置文件: ' + json.dataids;
            showSuccess(desc);
        },
        error: function( json ) {
            showError('导入配置组失败' + JSON.stringify(json.responseText));
        }
    });
}

function initBtn() {
    $('#import_btn').bind('click', function() {
        if (idcAutoComplete == null || $('#s_idc').val() == '' ||
            oldIdcAutoComplete == null || $('#s_srcidc').val() == '') {
            showInfoDlg('请先选择配置组和IDC。');
        } else {
            importPoolConfs(srcgroup, dstgroup, dstidc);
        }
    });
}

function main(url, tocken) {
    cmdburl = url;
    apitoken = tocken;
    initQueryParas();
    initBtn();
    initSrcGroup();
}
