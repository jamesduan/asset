# -*- coding: utf-8 -*-
from django.core.mail import EmailMessage
from util.Pika import Pika


def sendmail_html(subject, html_content, recipient_list, from_email='noreplay@cmdbapi.yihaodian.com.cn',
                  bcc=None, connection=None, attachments=None, headers=None, cc=None):
    msg = EmailMessage(subject, html_content, from_email, recipient_list, bcc, connection, attachments, headers, cc)
    msg.content_subtype = 'html'
    msg.send()


def sendmail_v2(subject, html_content, recipient_list, app=None,cc=[],from_email='noreplay@cmdbapi.yihaodian.com.cn'):
    message = {
        'sender': from_email,
        'receiver': ';'.join(recipient_list),
        'cc': ';'.join(cc),
        'subject': subject,
        'content': html_content,
        'app': app.id if app else 0,
        'app_name': '/'.join([app.site.name, app.name]) if app else 'unkonw'
    }
    amqp = Pika(message=message, exchange='message-exchange', routing_key='mailkey')
    return amqp.basic_publish()


def sendmail_co(subject, html_content, recipient_list, app=0, appname='',cc=[], from_email='noreplay@cmdbapi.yihaodian.com.cn'):
    message = {
        'sender': from_email,
        'receiver': ';'.join(recipient_list),
        'cc': ';'.join(cc),
        'subject': subject,
        'content': html_content,
        'app': app,
        'app_name': appname
    }
    amqp = Pika(message=message, exchange='message-exchange', routing_key='mailkey')
    return amqp.basic_publish()