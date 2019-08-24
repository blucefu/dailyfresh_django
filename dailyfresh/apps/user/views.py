from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.core.mail import send_mail

from django.contrib.auth import authenticate, login # 导入django自带的用户认证系统,导入login函数

from django.views.generic import View
from user.models import User

from itsdangerous import TimedJSONWebSignatureSerializer as Serializer # 导入加密类
from itsdangerous import SignatureExpired

from celery_tasks.tasks import send_register_active_email # 导入celery发送邮件函数

from django.http import HttpResponse

from django.conf import settings # 从dailyfresh里面settings导入SECRET_KEY 


from utils.mixin import LoginRequiredMixin # 先在utils目录下创建LoginRequiredMixin，再导入

# from django.contrib.auth.mixins import PermissionRequiredMixin # django 1.11里面直接导入

import re

# Create your views here.
def register(request):
    '''注册'''
    if request.method == 'GET':
        return render(request, 'register.html')
    else:
        # 接收数据
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        # 数据校验
        if not all([username, password, email]):
            return render(request, 'register.html', {'errmsg': '数据不完整'})
        # if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}{1,2})$', email):
        #     return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})
        
        # 用户名校验是否重复
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            user = None

        if user:
             return render(request, 'register.html', {'errmsg': '用户名已经存在'})
        # 进行业务处理：注册
        user = User.objects.create_user(username, password, email)

        # 默认没有激活
        user.is_active = 0
        user.save()
        # 返回应答
        return redirect(reverse('goods:index'))


def register_handle(request):
    '''注册处理'''
    pass
    
# 以后写视图，不要用函数，直接用视图类
# 先导入视图类from django.views.generic import Views
# 然后创建视图类

class RegisterView(View):
    '''注册'''
    def get(self, request):
        '''显示注册'''
        return render(request, 'register.html')
    def post(self, request):
        '''进行注册处理'''
         # 接收数据
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        # 数据校验
        if not all([username, password, email]):
            return render(request, 'register.html', {'errmsg': '数据不完整'})
        # if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}{1,2})$', email):
        #     return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})
        
        # 用户名校验是否重复
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            user = None

        if user:
             return render(request, 'register.html', {'errmsg': '用户名已经存在'})
        # 进行业务处理：注册
        user = User.objects.create_user(username, email, password)

        # 默认没有激活
        user.is_active = 0
        user.save()

        # 加密用户身份信息，生成激活token
        serializer = Serializer(settings.SECRET_KEY, 3600) # 创建加密对象
        info = {'confirm': user.id}
        token = serializer.dumps(info)
        token = token.decode() # token是字节码，需要转成字符串

        # 使用celery函数发邮件
        # 1 发出任务，任务放到redis数据库中
        send_register_active_email.delay(email, username, token)

        # 返回应答
        return redirect(reverse('goods:index'))


class ActiveView(View):
    '''用户激活'''
    def get(self, request, token):
        # 定义get方法,同时将urls.py中捕获的token传过来
        # 进行解密
        serializer = Serializer(settings.SECRET_KEY, 3600) # 创建加密对象
        try:
            info = serializer.loads(token)
            # 获取待激活用户id
            user_id = info['confirm']           
            # 根据id获取用户信息
            user = User.objects.get(id=user_id)
            # 修改用户激活状态并保存
            user.is_active = 1
            user.save()
            #激活后让用户跳转到登录页面
            return redirect(reverse('user:login'))
        except SignatureExpired as e:
            # 激活异常处理
            return HttpResponse('激活链接已经过期')
# user/login
class LoginView(View):
    '''用户登录'''
    def get(self, request):
        '''显示登录页面'''
        # 判断是否记住了用户名
        if 'username' in request.COOKIES:
            username = request.COOKIES.get('username')
            checked = 'checked'
        else:
            username = ''
            checked = ''
        # 使用模版
        return render(request, 'login.html', {'username': username, 'checked': checked})

    def post(self, request):
        '''登录校验'''
        # 接收数据
        username = request.POST.get('username')
        password = request.POST.get('pwd')
        # 校验数据
        if not all([username, password]):
            return render(request, 'login.html', {'errmsg': '数据不正确'})
        # 业务处理：登录校验  
        user = authenticate(username=username, password=password)
        # 用户名密码正确
        if user is not None:
            if user.is_active:
                # 用户已激活
                # 记录用户登录状态
                login(request, user)  # login函数是django用户认证系统里面的函数，存储到session 
                
                # 获取登录后要跳转的地址
                # 默认跳转到首页,如果 next 不为空，则跳转到 next
                next_url = request.GET.get('next', reverse('goods:index'))
                # response对象可以设置cookie,所以可以先生成response对象，再通过response对象调用cookie方法，最后再return response
                response = redirect(next_url)

                # 判断是否需要记录用户名
                remember = request.POST.get('remember')
                if remember == 'on':
                    # 记住用户名,使用cookie
                    response.set_cookie('username', username, max_age=7*24*3600)
                else:
                    response.delete_cookie('username')

                return response

            else:
                # 用户未激活
                return render(request, 'login.html', {'errmsg': '用户未激活'})
        # 用户名密码错误
        else:
            return render(request, 'login.html', {'errmsg': '用户名密码错误'})
        # 返回应答



# /user
class UserInfoView(LoginRequiredMixin, View):
    '''用户中心-信息页'''
    def get(self, request):
        '''显示'''
        # page = 'user'
        # Django使用会话和中间件来拦截request 对象到认证系统中。
        # 它们在每个请求上提供一个request.user属性，表示当前的用户
        # 如果用户未登录 -> request.user属性将设置成 AnonymousUser 的一个实例
        # 如果用户已登录 -> request.user属性将设置成 User 的一个实例
        # 传给user_center_info.html页面一个变量 page = info
        # 可以通过is_authenticated()区分 ，request.user.is_authenticated() 值不为空，表示用户已登录，否则表示用户未登录
        # 
        return render(request, 'user_center_info.html', {'page': 'user'})

# /user/order
class UserOrderView(LoginRequiredMixin, View):
    '''用户中心-订单页'''
    def get(self, request):
        '''显示'''
        # 传给user_center_order.html页面一个变量 page = order
        return render(request, 'user_center_order.html',  {'page': 'order'})

# /user/address
class UserSiteView(LoginRequiredMixin, View):
    '''用户中心-地址页'''
    def get(self, request):
        '''显示'''
        # 传给user_center_site.html页面一个变量 page = address
        return render(request, 'user_center_site.html', {'page': 'address'})

"""
 
# /user
class UserInfoView(PermissionRequiredMixin, View):
    '''用户中心-信息页'''
    permission_required = 'polls.can_edit'
    def get(self, request):
        '''显示'''
        # 传给user_center_info.html页面一个变量 page = info
        return render(request, 'user_center_info.html', {'page': 'user'})

# /user/order
class UserOrderView(PermissionRequiredMixin, View):
    '''用户中心-订单页'''
    def get(self, request):
        '''显示'''
        # 传给user_center_order.html页面一个变量 page = order
        return render(request, 'user_center_order.html',  {'page': 'order'})

# /user/address
class UserSiteView(PermissionRequiredMixin, View):
    '''用户中心-地址页'''
    def get(self, request):
        '''显示'''
        # 传给user_center_site.html页面一个变量 page = address
        return render(request, 'user_center_site.html', {'page': 'address'})

"""



























