/**
 * Created by liushuansheng on 2015/5/19.
 */

var filetypeAutoComplete = null;
var isConfigInfoTableCreated = false;

function operateFormatter(value, row, index) {
    var cmp = row.cmp%2;
    var hrefarr = [];
    if (cmp == 0) {
        hrefarr.push(
            '<a class="retrieve">',
                '<span class="glyphicon glyphicon-eye-open" style="cursor:pointer;margin-right:10px;">浏览</span>',
            '</a>');
        hrefarr.push(
            '<a class="edit">',
                '<span class="glyphicon glyphicon-edit" style="cursor:pointer;margin-right:10px;">编辑</span>',
            '</a>');
        hrefarr.push(
            '<a class="diff">',
                '<span class="glyphicon glyphicon-transfer" style="cursor:pointer;margin-right:10px;">到不一致</span>',
            '</a>');
    } else {
        hrefarr.push(
            '<a class="stg_retrieve">',
                '<span class="glyphicon glyphicon-eye-open" style="cursor:pointer;margin-right:10px;">stg浏览</span>',
            '</a>');
        hrefarr.push(
            '<a class="pro_retrieve">',
                '<span class="glyphicon glyphicn-eye-open" style="cursor:pointer;margin-right:10px;">pro浏览</span>',
            '</a>');
        hrefarr.push(
            '<a class="stg_edit">',
                '<span class="glyphicon glyphicon-edit" style="cursor:pointer;margin-right:10px;">stg编辑</span>',
            '</a>');
        hrefarr.push(
            '<a class="pro_edit">',
                '<span class="glyphicon glyphicn-edit" style="cursor:pointer;margin-right:10px;">pro编辑</span>',
            '</a>');
        hrefarr.push(
            '<a class="to_stg">',
                '<span class="glyphicon glyphicon-transfer" style="cursor:pointer;margin-right:10px;color:red;">到stg</span>',
            '</a>');
        hrefarr.push(
            '<a class="to_pro">',
                '<span class="glyphicon glyphicon-transfer" style="cursor:pointer;margin-right:10px;color:red;">到pro</span>',
            '</a>');
    }

    hrefarr.push(
        '<a class="remove">',
            '<span class="glyphicon glyphicon-remove" style="cursor:pointer;color:red;">删除</span>',
        '</a>');
    return hrefarr.join('');
}

function editConfigInfo(row, env, op) {
    var id = row.id;
    var dataid = row.data_id;
    var groupid = row.group_id;
    var idc = row.idc;
    var remark = row.remark;
    var cmp = row.cmp;
    if (env == 'staging')
        id = Math.floor(row.cmp/2);
    cmp = cmp%2;

    var inputdata = {
        'group_id': $("#group_id").val(),
        'idc': $("#idc").val(),
        'data_id': $("#data_id").val(),
        'env': env
    };
    $.ajax({
        url:  cmdburl + 'ycc/configinfo/' + id + '/',
        type: 'GET',
        async:  false,
        data: inputdata,
        headers: {'Authorization':'Token ' + apitoken},
        success: function( json ) {
            $("#e_id").val(id);
            $("#e_group_id").val(groupid);
            $("#e_idc").val(idc);
            $("#e_env").val(env);
            $("#e_data_id").val(dataid);
            $("#e_remark").val(remark);
            $("#e_content").val(json.content);
            $("#e_cmp").val(cmp);
            if (op == 'edit') {
                $('#editValueTitle').text('编辑' + dataid);
                $("#submit2").prop("disabled", false); 
            } else {
                $('#editValueTitle').text('浏览' + dataid);
                $("#submit2").prop("disabled", true); 
            }
            $('#editValue').modal('show');
        },
        error: function( json ) {
            showError('查询配置文件内容' + JSON.stringify(json.responseText));
        }
    });
}

function removeConfigInfo(e, value, row) {
    var configinfoid = row.id;
    var dataid = row.data_id;
    $.ajax({
        url:  cmdburl + 'ycc/configinfo/' + configinfoid + '/',
        type: 'DELETE',
        async:  false,
        headers: {'Authorization':'Token ' + apitoken},
        success: function( json ) {
            showSuccess('删除配置文件' + dataid);
            $('#configinfo').bootstrapTable('refresh', {
                silent: true
            });
        },
        error: function( json ) {
            showError('删除配置文件' + JSON.stringify(json.responseText));
        }
    });
}

function resetSameDiff(op, row) {
    var myDialog = z.widget('Dialog', {
        title:'警告！',
        html: '<p style="font-size:16px; color:#f00000;"><i class="fa fa-warning"></i> 确认要设置？</p>',
        buttons: {
            ok: '确认', 
            cancel: '取消'
        },
        ok: function() {
            resetSameDiffImp(op, row);
            myDialog.destroy();
        }
    }, true);
}

function resetSameDiffImp(op, row) {
    var dataid = row.data_id;
    var configinfoid = row.id;
    var stgid = row.cmp / 2;
    var content = row.content;
    var groupstatus = row.group_status;
    var inputdata = {
        'stgid': stgid,
        'op':op,
        'group_status':groupstatus,
        'content': content,
        'data_id': dataid
        //'cmp': stgid,
    };
    $.ajax({
        url:  cmdburl + 'ycc/configinfo/' + configinfoid + '/',
        type: 'PUT',
        async:  false,
        data: inputdata,
        headers: {'Authorization':'Token ' + apitoken},
        success: function( json ) {
            showSuccess('设置配置文件' + dataid);
            $('#configinfo').bootstrapTable('refresh', {
                silent: true
            });
        },
        error: function( json ) {
            showError('设置配置文件' + JSON.stringify(json.responseText));
        }
    });
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
                    removeConfigInfo(e, value, row);
                    myDialog.destroy();
                }
            }, true);
        },
        'click .edit': function (e, value, row) {
            editConfigInfo(row, 'both', 'edit');
        },
        'click .stg_edit': function (e, value, row) {
            editConfigInfo(row, 'staging', 'edit');
        },
        'click .pro_edit': function (e, value, row) {
            editConfigInfo(row, 'production', 'edit');
        },
        'click .retrieve': function (e, value, row) {
            editConfigInfo(row, 'both', 'retrieve');
        },
        'click .stg_retrieve': function (e, value, row) {
            editConfigInfo(row, 'staging', 'retrieve');
        },
        'click .pro_retrieve': function (e, value, row) {
            editConfigInfo(row, 'production', 'retrieve');
        },
        'click .diff': function ( e, value, row) {
            resetSameDiff(1, row);
        },
        'click .to_pro': function ( e, value, row) {
            resetSameDiff(2, row);
        },
        'click .to_stg': function ( e, value, row) {
            resetSameDiff(3, row);
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

    $('#attributeForm')
        .bootstrapValidator({
            fields: {
                group_id: {
                    validators: {
                        notEmpty: {
                            message: '配置组名不能为空。'
                        }
                    }
                },
                idc: {
                    validators: {
                        notEmpty: {
                            message: 'IDC不能为空。'
                        }
                    }
                },
                data_id: {
                    validators: {
                        notEmpty: {
                            message: '配置文件名不能为空。'
                        }
                    }
                },
                content: {
                    validators: {
                        notEmpty: {
                            message: '配置文件内容不能为空。'
                        }
                    }
                }
            }
        })
        .on('success.form.bv', function(e) {
            e.preventDefault();
            var inputdata = {
                'group_status': $("#s_group_status").val(),
                'group_id': $("#s_group").val(),
                'idc': $("#idc").val(),
                'data_id': $("#data_id").val(),
                'remark': $("#remark").val(),
                'content': $("#content").val(),
                'file_type': $("#file_type").val(),
                'cmp': $("#cmp").val()
            };
            $.ajax({
                url: cmdburl + 'ycc/configinfo/',
                type: 'POST',
                async:  false,
                data: inputdata,
                headers: {'Authorization':'Token ' + apitoken},
                success: function( json ) {
                    showSuccess('添加配置文件' + json.data_id);
                    $('#addValue').modal('hide');
                    $('#attributeForm').bootstrapValidator('resetForm', true);
                    if (isConfigInfoTableCreated) {
                        $('#configinfo').bootstrapTable('refresh', {
                            silent: true
                        });
                    } else {
                        listConfigInfos();
                    }
                },
                error: function( json ) {
                    showError('添加配置文件' + JSON.stringify(json.responseText));
                    $('#addValue').modal('hide');
                }
            });

            $("#group_id").val('');
            $("#idc").val('');
            $("#data_id").val('');
            $("#remark").val('');
            $("#content").val('');
        });


    $('#attributeForm2')
        .bootstrapValidator({
            fields: {
                content: {
                    validators: {
                        notEmpty: {
                            message: '配置文件内容不能为空。'
                        }
                    }
                }
            }
        })
        .on('success.form.bv', function(e) {
            e.preventDefault();
            var env = $("#e_env").val();
            if (env == 'both')
                env = 'production';
            var inputdata = {
                'group_status': $("#s_group_status").val(),
                'group_id': $("#e_group_id").val(),
                'idc': $("#e_idc").val(),
                'env': env,
                'data_id': $("#e_data_id").val(),
                'remark': $("#e_remark").val(),
                'content': $("#e_content").val(),
                'file_type': $("#e_file_type").val(),
                'cmp': $("#e_cmp").val()
            };
            $.ajax({
                url: cmdburl + 'ycc/configinfo/' + $("#e_id").val() + '/',
                type: 'PUT',
                async:  false,
                data: inputdata,
                headers: {'Authorization':'Token ' + apitoken},
                success: function( json ) {
                    showSuccess('编辑配置文件' + json.data_id);
                    $('#editValue').modal('hide');
                    $('#attributeForm2').bootstrapValidator('resetForm', true);
                    $('#configinfo').bootstrapTable('refresh', {
                        silent: true
                    });
                },
                error: function( json ) {
                    showError('修改配置文件' + JSON.stringify(json.responseText));
                    $('#editValue').modal('hide');
                }
            });
        });
}

function listConfigInfos() {
    var groupid = 0;
    if (idcAutoComplete != null)
        groupid = idcAutoComplete.getSelected().value;
    var filetype = $('#s_filetype').val();
    var keyword = $('#s_key').val();
    var url = cmdburl + 'ycc/configinfo/?format=json&groupid=' + groupid + '&filetype=' + filetype + '&keyword=' + keyword;

    if (!isConfigInfoTableCreated) {
        $('#configinfo').bootstrapTable({
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
                    field: 'group_status',
                    visible: false
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
                    //title: '对比结果',
                    //align: 'center'
                    visible: false
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
        isConfigInfoTableCreated = true;
    } else {
        $('#configinfo').bootstrapTable('refresh', {
            silent: true,
            url: url
        });
    }
}

function sub2audit() {
    var groupid = idcAutoComplete.getSelected().value;
    var row = {'group_id': groupid, 'version': 0};
    initDlg(row, 0);
    $('#listdataidstatus').modal();
}

function initBtn() {
    $('#query_btn').bind('click', function() {
        if (idcAutoComplete == null || $('#s_idc').val() == '') {
            showInfoDlg('请先选择配置组和IDC。');
        } else {
            listConfigInfos();
        }
    });
    $('#create_btn').bind('click', function() {
        if (idcAutoComplete == null || $('#s_idc').val() == '') {
            showInfoDlg('请先选择配置组和IDC。');
        } else {
            $('#group_id').val($('#s_group').val());
            $('#idc').val($('#s_idc').val());
            $('#addValue').modal();
        }
    });
    $('#sub2audit_btn').bind('click', function() {
        if (idcAutoComplete == null || $('#s_idc').val() == '') {
            showInfoDlg('请先选择配置组和IDC。');
        } else {
            sub2audit();
        }
    });
}

function initFiletypeAutoComplete() {
    var filetypelist = [{text:'txt', value:'txt'}, {text:'db', value:'db'}];
    if (filetypeAutoComplete)
        filetypeAutoComplete.destroy();
    filetypeAutoComplete = z.widget('AutoComplete', {
        renderTo: 's_filetype',
        dropDown: true,
        optionList: sortArr(filetypelist),
        onSelected: function(t, v) {
        }
    });
}

function main(url, tocken) {
    cmdburl = url;
    apitoken = tocken;
    registerAction();
    initFiletypeAutoComplete();
    initQueryParas();
    initBtn();
    initBaseBtn();
    initDiffDlgCloseEvent();
}
