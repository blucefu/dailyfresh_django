from django.conf import settings
from django.core.mail import send_mail
from celery import Celery
import time

# 注意，django 的 1.8.2 对应的 celery 版本支持 4.1.0,celery再高的就不匹配了
# 创建celery队列实例对象
app = Celery('celery_tasks.tasks', broker='redis://127.0.0.1:6379/8')

# 定义任务函数
@app.task
def send_register_active_email(to_email, username, token):
    '''发送激活邮件'''
    # 组织邮件
    # 发送邮件  
    subject = '天天生鲜欢迎信息'
    message = ''
    sender = settings.EMAIL_FROM
    receiver = [to_email]
    html_message = '<h1>%s，欢迎成为会员</h1>点击链接即可激活<br/><a href="http://127.0.0.1:8000/user/active/%s">http://127.0.0.1:8000/user/active/%s</a>' % (username, token, token)  
    send_mail(subject, message, sender, receiver, html_message=html_message)
