/**
 * Created by wuzhiqiang on 2017/1/17.
 */
/** 区分ios 和 安卓 加载不同的css **/
var u = navigator.userAgent, app = navigator.appVersion;
var isiOS = !!u.match(/\(i[^;]+;( U;)? CPU.+Mac OS X/); //ios终端
var link = document.createElement("link");
link.type = "text/css";
link.rel = "stylesheet";
if(isiOS){
    link.href = "/staticv2/cmdbv2/mobile/css/app_ios.css";
}else{
    link.href = "/staticv2/cmdbv2/mobile/css/app_android.css";
}
document.getElementsByTagName("head")[0].appendChild(link);
