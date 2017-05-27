/**
 * Created by liushuansheng on 2015/6/8.idcAutoComplete
 */

groupAutoComplete = null;
idcAutoComplete = null;

cmdburl = null;
apitoken= null;

//begin for sub2audit, audit, publishe dlg button
var groupnameIdcMap = {};
var listdataidstatus = 0;
var isDlgTableCreated = false;
var opgroupmethod = null;
var opgroupid= null;
var opgroupversion= null;
var listdataidstatus= null;
var dlgTitle = null;
//end for sub2audit, audit, publishe dlg button

var loading_ico = $('<div><img src="/staticv2/cmdbv2/ycc/img/loading.gif" /></div>').css({
    position: 'absolute',
    zIndex: 9999,
    top: '50%',
    left: '50%'
});

var loading_mask = $('<div></div>').css({
    height: Math.max($(window).height(), $('body').height()),
    width: '100%',
    position: 'absolute',
    zIndex: 9999,
    top: 0,
    left: 0
});

function endLoading() {
    loading_mask.remove();
    loading_ico.remove();
}

function showLoading() {
    endLoading();
    loading_mask.appendTo('body');
    loading_ico.appendTo('body');
}


function sortArr(arr) {
    arr.sort(function(a, b) {
        var astr = a.text.toLowerCase();
        var bstr = b.text.toLowerCase();
        if (astr > bstr)
            return 1;
        else if (astr < bstr)
            return -1;
        else
            return 0;
    });
    return arr;
}

function showInfoDlg(info) {
    var myDialog = z.widget('Dialog', {
        title:'提示！',
        html: '<p style="font-size:16px; color:#f00000;"><i class="fa fa-info"></i> ' + info + ' </p>',
        buttons: {
            ok: '确认',
            cancel: ''
        },
        ok: function() {
            myDialog.destroy();
        }
    }, true);
}

function showSuccess(info) {
    $('#alert').empty().append('<div class="alert alert-success text-center" role="alert">' +
                                    '<button type="button" class="close" data-dismiss="alert" aria-label="Close">' +
                                        '<span aria-hidden="true">&times;</span>' +
                                    '</button>' +
                                    '<strong>成功</strong>' + info +
                                '</div>');
}

function showError(err) {
    $('#alert').empty().append('<div class="alert alert-danger text-center" role="alert">' +
                                    '<button type="button" class="close" data-dismiss="alert" aria-label="Close">' +
                                        '<span aria-hidden="true">&times;</span>' +
                                    '</button>' +
                                    '<strong>错误!</strong>' + err +
                                '</div>');
}

function initAutoCompleteEvent() {
    $('#s_group').bind('keyup', function() {
        if($(this).val() == '') {
            if (idcAutoComplete) {
                idcAutoComplete.destroy();
                idcAutoComplete = null;
            }
            $('#s_idc').val('');
            $('#s_idc').prop("title", "");
        }
    });
    $('#s_group').val('');
    $('#s_idc').val('');
}

function setConfigGroupStatus() {
    var groupid = $('#s_group').val();
    var idc = idcAutoComplete.getSelected().value;
    $.ajax({
        url:  cmdburl + 'ycc/status/?format=json&groupid=' + groupid + '&idc=' + idc + '&status=' + 0 + '&auditor=\'\'',
        type: 'GET',
        async:  false,
        headers: {'Authorization':'Token ' + apitoken},
        success: function( json ) {
            $('#s_group_status').val(json.results[0].id);
        },
        error: function( json ) {
            showError('获取配置组状态失败' + JSON.stringify(json.responseText));
        }
    });
}

function initIdcAutoComplete(idclist) {
    $('#s_idc').val('');
    if (idcAutoComplete)
        idcAutoComplete.destroy();
    idcAutoComplete = z.widget('AutoComplete', {
        renderTo: 's_idc',
        dropDown: true,
        optionList: sortArr(idclist),
        onSelected: function(t, v) {
            setConfigGroupStatus();
        }
    });
    if (idclist.length == 1) {
        $('#s_idc').val(idclist[0].text);
        setConfigGroupStatus();
    }
}

function initGroupAutoComplete(json) {
    var  grouplist = [];
    var groupnamelist = [];

    $.each(json.results, function(index, value) {
        var groupname = value.group_id;
        if (groupnamelist.indexOf(groupname) == -1) {
            grouplist.push({
                text: groupname,
                value: value
            });
            groupnamelist.push(groupname);
        }
        if (!groupnameIdcMap.hasOwnProperty(groupname))
            groupnameIdcMap[groupname] = [];
        groupnameIdcMap[groupname].push({
            text: value.idc_name,
            value: value.idc
        });
    });

    if (groupAutoComplete)
        groupAutoComplete.destroy();
    groupAutoComplete = z.widget('AutoComplete', {
        renderTo: 's_group',
        dropDown: true,
        optionList: sortArr(grouplist),
        onSelected: function(t, v) {
            initIdcAutoComplete(groupnameIdcMap[t]);
        }
    });
}

function initQueryParas() {
    initAutoCompleteEvent();
    $.ajax({
        url: cmdburl + 'ycc/group/?format=json&page_size=5000&page=1',
        type: 'GET',
        async: false,
        headers: {'Authorization':'Token ' + apitoken},
        success: function ( json ) {
            initGroupAutoComplete(json);
        },
        error: function ( json ) {
            showError('查询配置组失败' + JSON.stringify(json.responseText));
        }
    });
}


function cmpstgFormatter(value, row, index) {
    var cmp = row.cmp;
    var hrefarr = [];
    var desc = '相同';
    var colorStyle = '';
    if (cmp != 0) {
        desc = '不同';
        colorStyle = ' style="color:red;"';
    }
    hrefarr.push(
            '<a class="viewcmpstg">',
                '<span class="glyphicon glyphicon-info-sign"' + colorStyle + '>' + desc + '</span>',
            '</a>');
    return hrefarr.join('');
}

function cmpproFormatter(value, row, index) {
    var cmp2 = row.cmp2;
    var hrefarr = [];
    var desc = '相同';
    var colorStyle = '';
    if (cmp2 == 0) {
        desc = '相同';
    } else if (cmp2 == 1) {
        desc = '不同';
        colorStyle = ' style="color:red;"';
    } else if (cmp2 == 2) {
        desc = '新增';
    } else if (cmp2 == 3) {
        desc = '删除';
        colorStyle = ' style="color:red;"';
    } else {
        desc = '未知';
        colorStyle = ' style="color:red;"';
    }
    hrefarr.push(
            '<a class="viewcmppro">',
                '<span class="glyphicon glyphicon-info-sign"' + colorStyle + '>' + desc + '</span>',
            '</a>');
    return hrefarr.join('');
}

function diffUsingJS(content1, content2, env) {
    content1 = difflib.stringAsLines(content1);
    content2 = difflib.stringAsLines(content2);
    if (content1 == '')
        content1 = [];
    if (content2 == '')
        content2 = [];
    var sm = new difflib.SequenceMatcher(content1, content2);
    var opcodes = sm.get_opcodes();
    var diffoutputdiv = document.getElementById("diffoutput");
    while (diffoutputdiv.firstChild)
        diffoutputdiv.removeChild(diffoutputdiv.firstChild);
    var contextSize = 1;
    contextSize = contextSize ? contextSize : null;
    diffoutputdiv.appendChild(diffview.buildView({ baseTextLines:content1,
                                                   newTextLines:content2,
                                                   opcodes:opcodes,
                                                   baseTextName:env,
                                                   newTextName:"current",
                                                   contextSize:contextSize,
                                                   viewType: 0}));
    
}

function initDiffDlg(row, env, cmp) {
    var diffTitle = '对比' + ':' + row.data_id;
    $('#diffTitle').text(diffTitle);
    var proid = row.id;
    $.ajax({
        url:  cmdburl + 'ycc/diffcontent/?' + 'proid=' + proid + '&env=' + env + '&cmp=' + cmp,
        type: 'GET',
        async:  false,
        headers: {'Authorization':'Token ' + apitoken},
        success: function( json ) {
            $('#listdataidstatus').modal('hide');
            diffUsingJS(json.cmpcontent, json.curcontent, env);
        },
        error: function( json ) {
            showError('查询配置文件内容' + JSON.stringify(json.responseText));
        }
    });
}

function listDataidStatusInGroup() {
    var status = listdataidstatus;
    var url = cmdburl + 'ycc/configstatus/?format=json&groupid=' + opgroupid +'&version=' + opgroupversion + '&status=' + status;
    if (!isDlgTableCreated) {
        $('#configinfo2').bootstrapTable({
            url: url,
            ajaxOptions: {'headers': {'Authorization': 'Token ' + apitoken}},
            columns: [
                {
                    field: 'id',
                    visible: false
                },
                {
                    field: 'data_id',
                    title: '配置文件',
                    align: 'center'
                },
                {
                    field: 'group_id',
                    title: '配置组',
                    align: 'center'
                },
                {
                    field: 'idc',
                    title: 'IDC',
                    align: 'center'
                },
                {
                    field: 'version',
                    title: '配置组版本',
                    align: 'center'
                },
                {
                    field: 'remark',
                    title: '说明',
                    align: 'center'
                },
                {
                    field: 'file_type',
                    title: '文件类型',
                    align: 'center'
                },
                {
                    field: 'cmp',
                    title: '跟stg对比',
                    align: 'center',
                    formatter: cmpstgFormatter,
                    events: operateEvents
                },
                {
                    field: 'cmp2',
                    title: '跟pro对比',
                    align: 'center',
                    formatter: cmpproFormatter,
                    events: operateEvents
                }
            ],
            responseHandler: function (res) {
                var result = {};
                result.rows = res.results;
                result.total = res.count;
                //if (result.results.length == 0)
                //    document.getElementById('submit3').disabled = true;
                return result
            },
            queryParams: function (p) {
                return {
                    page_size: p.limit,
                    page: p.offset / p.limit + 1,
                    search: p.search
                };
            },
            pagination: true,
            pageSize: 50,
            pageList: [10, 20, 100],
            sidePagination: 'server',
            showRefresh: false,
            search: false,
            showColumns: false,
            //toolbar: "#toolbar",
            cache: false
        });
        isDlgTableCreated = true;
    } else {
        $('#configinfo2').bootstrapTable('refresh', {
            silent: true,
            url: url
        });
    }
}

function groupAjaxOp() {
    $.ajax({
        url: cmdburl + 'ycc/configstatus/?groupid=' + opgroupid + '&version=' + opgroupversion + '&status=' + listdataidstatus,
        type: opgroupmethod,
        async: false,
        headers: {'Authorization':'Token ' + apitoken},
        success: function( json ) {
            if (json['result']) {
                showSuccess(dlgTitle);
                document.getElementById("query_btn").click();
            }
            else
                showError(json['desc']);
            $('#listdataidstatus').modal('hide');
        },
        error: function( json ) {
            showError(dlgTitle + JSON.stringify(json.responseText));
            $('#listdataidstatus').modal('hide');
        }
    });
}

function submit3Fun() {
    groupAjaxOp();
}

function initBaseBtn() {
    $('#submit3').bind('click', function() {
        submit3Fun();
    });
}

function initDiffDlgCloseEvent() {
    $('#diff').on('hidden.bs.modal', function (e) {
        $('#listdataidstatus').modal();
    });
}

function initDlg(row, status) {
    var groupid = row.group_id;
    var version = row.version;
    listdataidstatus = status;
    opgroupmethod = 'GET';
    dlgTitle = '';
    opgroupid = groupid;
    opgroupversion = version;
    if (listdataidstatus == -1) {
        listdataidstatus = row.status;
        dlgTitle = '浏览';
        $("#submit3").prop("disabled", true); 
    } else if (listdataidstatus == 0) {
        dlgTitle = '提交审核';
        opgroupmethod = 'POST';
        $("#submit3").prop("disabled", false);
    } else if (listdataidstatus == 1) {
        dlgTitle = '审核';
        opgroupmethod = 'PUT';
        $("#submit3").prop("disabled", false);
    } else if (listdataidstatus == 2) {
        dlgTitle = '发布';
        opgroupmethod = 'PUT';
        $("#submit3").prop("disabled", false);
    } else if (listdataidstatus == 5) {
        dlgTitle = '回滚';
        opgroupmethod = 'PUT';
        $("#submit3").prop("disabled", false);
    }
    $('#listdataidstatusTitle').text(dlgTitle);
    listDataidStatusInGroup();

    $('#listdataidstatus').modal();
}
