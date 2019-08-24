from django.conf.urls import url

from django.contrib.auth.decorators import login_required # 导入用户认证的装饰器
# 具体参考django 1.11 中的认证系统 https://www.yiyibooks.cn/xx/Django_1.11.6/topics/auth/default.html

# from user import views 使用视图类后就不需要这样写了
from user.views import RegisterView, ActiveView, LoginView, UserInfoView, UserOrderView, UserSiteView

urlpatterns = [
    # url(r'^register$', views.register, name='register'), # name='register'用于反向解析
    # url(r'^register_handle$', views.register_handle, name='register_handle'), 
    # 注册处理函数可以写在register里面，根据不同的请求方式,get是请求注册页面，post是处理注册
    url(r'^register$', RegisterView.as_view(), name='register'), # 使用类视图注册
    # as_view() 方法是 views视图类自带的方法，RegisterView类并没有写该方法
    url(r'^active/(?P<token>.*)$', ActiveView.as_view(), name='active'), # 用户激活
    # (?P<token>.*) 中 P<token> 表示捕获token
    url(r'^login$', LoginView.as_view(), name='login'), # 用户登录
    
    url(r'^$', login_required(UserInfoView.as_view()), name='user'), # 个人中心-信息页
    url(r'^order$', login_required(UserOrderView.as_view()), name='order'), # 个人中心-订单页
    url(r'^address$', login_required(UserSiteView.as_view()), name='address'), # 个人中心-地址页
 
]
