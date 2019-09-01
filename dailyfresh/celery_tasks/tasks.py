from django.conf import settings
from django.core.mail import send_mail

from django.template import loader, RequestContext

from celery import Celery
import time


# 在任务处理者一端加这几句
import os
# import django
# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dailyfresh.settings")
# django.setup()


from goods.models import GoodsType, GoodsSKU, IndexGoodsBanner, IndexPromotionBanner, IndexTypeGoodsBanner
from django_redis import get_redis_connection


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

@app.task
def generate_static_index_html():
    '''产生静态页面首页'''
    # 获取首页商品种类信息
    types = GoodsType.objects.all()
    # 获取首页banner商品信息
    goods_banners = IndexGoodsBanner.objects.all().order_by('index') # -index从大到小,index从小到大
    # 获取首页频道促销信息
    promotion_banners = IndexPromotionBanner.objects.all().order_by('index')
    # 获取首页商品分类展示信息
    for type in types:
        # 获取type种类首页分类商品的图片展示信息
        image_banners = IndexTypeGoodsBanner.objects.filter(type=type, display_type=1).order_by('index')
        # 获取type种类首页分类商品的文字展示信息
        title_banners = IndexTypeGoodsBanner.objects.filter(type=type, display_type=0).order_by('index')

        # 动态给tpye增加属性
        type.image_banners = image_banners
        type.title_banners = title_banners


    # type_goods_banners = IndexTypeGoodsBanner.objects.all() 不能直接获取图片，
    # 获取用户购物车商品数目

    # 组织上下文
    context = {'types': types,
                'goods_banners': goods_banners,
                'promotion_banners': promotion_banners,}
    # 使用模版
        # return render(request, 'static_index.html', context) # 然后需要到模版中使用数据

    # 1 加载模版文件，返回模版对象
    temp = loader.get_template('static_index.html')
    # 2 定义上下文
    # 3 模版渲染
    static_index_html = temp.render(context) # static_index_html即为渲染的文件内容，里面包含html文件及需要传的数据
    # 生成首页对应的静态文件
    save_path = os.path.join(settings.BASE_DIR, 'static/index.html') # 创建文件路径，settings.BASE_DIR为项目根目录
    with open(save_path, 'w') as f:
        f.write(static_index_html)

