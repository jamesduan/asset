/**
 * Created by liushuansheng on 2015/6/8.
 */

var groupStatusAutoComplete = null;
var isStatusTableCreated = false;

function initGroupStatusAutoComplete() {
    var statuslist = [{text:'edit', value:'0'}, {text:'commited', value:'1'},
    					{text:'approved', value:'2'}, {text:'rejected', value:'3'},
    					{text:'published', value:'4'}, {text:'history', value:'5'}];
    if (groupStatusAutoComplete)
        groupStatusAutoComplete.destroy();
    groupStatusAutoComplete = z.widget('AutoComplete', {
        renderTo: 's_status',
        dropDown: true,
        optionList: sortArr(statuslist),
        onSelected: function(t, v) {
        }
    });
}

function operateFormatter(value, row, index) {
    var status = row.status;
    var hrefarr = [];
	hrefarr.push(
            '<a class="retrieve">',
                '<span class="glyphicon glyphicon-eye-open" style="cursor:pointer;margin-right:10px;">浏览</span>',
            '</a>');
    // if this group staus is commited, it could be audited
    if (status == 1) {
        
    hrefarr.push(
            '<a class="audit">',
                '<span class="glyphicon glyphicon-check" style="cursor:pointer;margin-right:10px;">审核</span>',
            '</a>');
    }
    // if this group staus is approved, it could be published
    if (status == 2) {
        hrefarr.push(
            '<a class="publish">',
                '<span class="glyphicon glyphicon-ok-sign" style="cursor:pointer;margin-right:10px;">发布</span>',
            '</a>');
    };
    // if this group staus is history, it could be rollbacked
    if (status == 5) {
        hrefarr.push(
            '<a class="rollback">',
                '<span class="glyphicon glyphicon-backward" style="cursor:pointer;margin-right:10px;color:red;">回滚</span>',
            '</a>');
    }
    // if this group staus is not published/edit, it could be removed
    if (status != 4 && status != 0) {
        hrefarr.push(
            '<a class="remove">',
                '<span class="glyphicon glyphicon-remove" style="cursor:pointer;color:red;">删除</span>',
            '</a>');
    }
    return hrefarr.join('');
}

function listConfigGroup(e, value, row) {
    initDlg(row, -1);
}

function auditConfigGroup(e, value, row) {
    initDlg(row, 1);
}

function publishConfigGroup(e, value, row) {
    initDlg(row, 2);
}

function rollbackConfigGroup(e, value, row) {
    initDlg(row, 5);
}

function registerAction() {
	window.operateEvents = {
        'click .remove': function (e, value, row) {
            var myDialog = z.widget('Dialog', {
                title:'警告！',
                html: '<p style="font-size:16px; color:#f00000;"><i class="fa fa-warning"></i> 确认要删除？</p>',
                buttons: {
                    ok: '确认', 
                    cancel: '取消'
                },
                ok: function() {
                    removeConfigGroupVersion(e, value, row);
                    myDialog.destroy();
                }
            }, true);
        },
        'click .audit': function (e, value, row) {
            auditConfigGroup(e, value, row);
        },
        'click .publish': function (e, value, row) {
            publishConfigGroup(e, value, row);
        },
        'click .rollback': function (e, value, row) {
            rollbackConfigGroup(e, value, row);
        },
        'click .retrieve': function (e, value, row) {
            listConfigGroup(e, value, row);
        },
        'click .viewcmpstg': function (e, value, row) {
            initDiffDlg(row, 'staging', row.cmp);
            $('#diff').modal();
        },
        'click .viewcmppro': function (e, value, row) {
            initDiffDlg(row, 'production', row.cmp2);
            $('#diff').modal();
        }
    };

}

function removeConfigGroupVersion(e, value, row) {
    var groupstatusid = row.id;
    var version = row.version;
    $.ajax({
        url:  cmdburl + 'ycc/status/' + groupstatusid + '/',
        type: 'DELETE',
        async:  false,
        headers: {'Authorization':'Token ' + apitoken},
        success: function( json ) {
            showSuccess('删除配置组版本' + version);
            $('#group').bootstrapTable('refresh', {
                silent: true
            });
        },
        error: function( json ) {
            showError('删除配置文件' + JSON.stringify(json.responseText));
        }
    });
}

function listGroupWithStatus() {
	var groupid = '';
	var idc = '';
    if (groupAutoComplete != null)
        groupid = $('#s_group').val();
    if (idcAutoComplete != null)
        idc = $('#s_idc').val();
    var status = 100;
    var statusSelected = groupStatusAutoComplete.getSelected();
    if (statusSelected != null)
        status = statusSelected.value;
    var auditor = $('#s_auditor').val();
    var url = cmdburl + 'ycc/status/?format=json&groupid=' + groupid + '&idc=' + idc + '&status=' + status + '&auditor=' + auditor;

    if (!isStatusTableCreated) {
    	$('#group').bootstrapTable({
    		url: url,
    		ajaxOptions: {'headers': {'Authorization': 'Token ' + apitoken}},
    		columns: [
                {
                    field: 'id',
                    visible: false
                },
                {
                    field: 'group_id',
                    visible: false
                },
                {
                    field: 'group_id_desc',
                    title: '配置组',
                    align: 'center'
                },
                {
                    field: 'idc',
                    title: 'IDC',
                    align: 'center'
                },
                {
                    field: 'remark',
                    title: '说明',
                    align: 'center'
                },
                {
                    field: 'version',
                    title: '版本',
                    align: 'center'
                },
                {
                    field: 'status',
                    visible: false
                },
                {
                    field: 'status_desc',
                    title: '状态',
                    align: 'center'
                },
                {
                    field: 'pre_version',
                    title: '前驱版本',
                    align: 'center'
                },
                {
                    field: 'operate',
                    title: '操作',
                    align: 'center',
                    formatter: operateFormatter,
                    events: operateEvents
                }
            ],
    		responseHandler: function (res) {
                var result = {};
                result.rows = res.results;
                result.total = res.count;
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
		isStatusTableCreated = true;
    } else {
        $('#group').bootstrapTable('refresh', {
            silent: true,
            url: url
        });
    }
}

function initBtn() {
    $('#query_btn').bind('click', function() {
        listGroupWithStatus();
    });
}

function main(url, tocken) {
	cmdburl = url;
	apitoken = tocken;
	registerAction();
	initGroupStatusAutoComplete();
	initQueryParas();
	initBtn();
	initBaseBtn();
	initDiffDlgCloseEvent();
}
