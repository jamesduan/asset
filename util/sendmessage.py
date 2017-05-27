from util.Pika import Pika

def sendmessage_v2( app, appname, message_content, recipient_list, from_message='noreplay@cmdbapi.yihaodian.com.cn'):
    message = {
        'app': app,
        'app_name': appname,
        'content':  message_content,
        'receiver': recipient_list,
        'cc':'',
        'sender': from_message,
    }
    amqp = Pika(message=message, exchange='message-exchange', routing_key='smskey')
    return amqp.basic_publish()
